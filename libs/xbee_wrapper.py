#! /usr/bin/python
# -*- coding: utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

#   Xbee to MQTT gateway
#   Copyright (C) 2012 by Xose Pérez
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = "Xose Pérez"
__contact__ = "xose.perez@gmail.com"
__copyright__ = "Copyright (C) 2013 Xose Pérez"
__license__ = 'GPL v3'

import os
import re
import glob
import binascii
import logging
import time
from xbee import ZigBee

class XBeeWrapper(object):
    """
    Helper class for the python-xbee module.
    It processes API packets into simple address/port/value groups.
    See http://code.google.com/r/xoseperez-python-xbee/
    """

    default_port_name = 'serial'

    serial = None
    xbee = None
    logger = None

    buffer = dict()

    def log(self, level, message):
        if self.logger:
            self.logger.log(level, message)

    def disconnect(self):
        """
        Closes serial port
        """
        self.xbee.halt()
        self.serial.close()
        return True

    def connect(self):
        """
        Creates an Xbee instance
        """
        try:
            self.log(logging.INFO, "Connecting to Xbee")
            self.xbee = ZigBee(self.serial, callback=self.process)
        except:
            return False
        return True

    def process(self, packet):
        """
        Processes an incoming packet, supported packet frame ids:
            0x90: Zigbee Receive Packet
            0x92: ZigBee IO Data Sample Rx Indicator
        """

        self.log(logging.DEBUG, packet)

        address = binascii.hexlify(packet['source_addr_long'])
        #frame_id = int(packet['frame_id'])
        id = packet['id']
        if(id == "rx_io_data_long_addr"):
            frame_id = 92

        # Data sent through the serial connection of the remote radio
        if (frame_id == 90):

            # Some streams arrive split in different packets
            # we buffer the data until we get an EOL
            self.buffer[address] = self.buffer.get(address,'') + packet['data']
            count = self.buffer[address].count('\n')
            if (count):
                lines = self.buffer[address].splitlines()
                try:
                    self.buffer[address] = lines[count:][0]
                except:
                    self.buffer[address] = ''
                for line in lines[:count]:
                    line = line.rstrip()
                    try:
                        port, value = line.split(':', 1)
                    except:
                        value = line
                        port = self.default_port_name
                    self.on_message(address, port, value)

        # Data received from an IO data sample
        if (frame_id == 92):
            for sample in packet['samples']:
                self.log(logging.DEBUG, sample)
                for port in sample.keys():
                    value = sample[port]
                    if port[:3] == 'dio':
                        value = 1 if value else 0
                    self.on_message(address, port, value)

    def on_message(self, address, port, value):
        """
        Hook for outgoing messages.
        """
        None

    def toggle_port(self, address, port):
        """
        Sends a message to a remote radio to set a pin HIGH, pause for a moment, then set it LOW
        """
        txt_addr = address
        self.log(logging.DEBUG, "in toggle_port %s@%s" % (port, address))
        if port[:3] == 'dio':
            address = binascii.unhexlify(address)
            number = int(port[4:])
            command = 'P%d' % (number - 10) if number>9 else 'D%d' % number
            self.log(logging.DEBUG, "toggle_port, command: %s" % (command))
            self.xbee.remote_at(dest_addr_long = address, command = command, parameter = b'\x05', options=b'\x02')
            self.log(logging.DEBUG, "Set %s@%s to HIGH" % (command, txt_addr))
            time.sleep(.2)
            self.xbee.remote_at(dest_addr_long = address, command = command, parameter = b'\x04', options=b'\x02')
            self.log(logging.DEBUG, "Set %s@%s to LOW" % (command, txt_addr))
            return True

        return False

    def send_message(self, address, port, value, permanent = True):
        """
        Sends a message to a remote radio
        Currently, this only supports setting a digital output pin LOW (4) or HIGH (5)
        """
        if port[:3] == 'dio':
            address = binascii.unhexlify(address)
            number = int(port[3:])
            command = 'P%d' % (number - 10) if number>9 else 'D%d' % number
            value = binascii.unhexlify('0' + str(int(value) + 4))
            self.xbee.remote_at(dest_addr_long = address, command = command, parameter = value)
            self.xbee.remote_at(dest_addr_long = address, command = 'WR' if permanent else 'AC')
            return True

        return False

    def find_devices(self, vendor_id = None, product_id = None):
        """
        Looks for USB devices
        optionally filtering by with the provided vendor and product IDs
        """
        devices = []

        for dn in glob.glob('/sys/bus/usb/devices/*'):
            try:
                vid = int(open(os.path.join(dn, "idVendor" )).read().strip(), 16)
                pid = int(open(os.path.join(dn, "idProduct")).read().strip(), 16)
                if ((vendor_id is None) or (vid == vendor_id)) and ((product_id is None) or (pid == product_id)):
                    dns = glob.glob(os.path.join(dn, os.path.basename(dn) + "*"))
                    for sdn in dns:
                        for fn in glob.glob(os.path.join(sdn, "*")):
                            if  re.search(r"\/ttyUSB[0-9]+$", fn):
                                devices.append(os.path.join("/dev", os.path.basename(fn)))
                            pass
                        pass
                    pass
                pass
            except ( ValueError, TypeError, AttributeError, OSError, IOError ):
                pass
            pass

        return devices

