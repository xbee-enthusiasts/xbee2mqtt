#!/usr/bin/python

from Crypto.Cipher import AES
from Crypto import Random
import binascii
import time


class MACUtil:
    rndfile = None
    def __init__(self):
        self.rndfile = Random.new()

    def create_mac(self, key):
        """ Encrypt a timestamp with the secret key """
        iv = self.rndfile.read(AES.block_size)
        ts = str(int(time.time() * 1000))

        # pad timestamp & key to a multiple of 16
        while len(ts) < 16:
            ts += ' '
        while len(ts) % 16 != 0: 
            ts += ' '

        aes = AES.new(key, AES.MODE_CBC, iv)
        ciphertext = aes.encrypt(ts)
        msg = str(binascii.hexlify(iv)) + str(binascii.hexlify(ciphertext))
        return msg

    def authenticate_mac(self, key, msg, thresh_millis=5000):
        """ Check that message created with the format of create_mac() is authentic """
        iv = binascii.unhexlify(msg[0:32])              # the first 32 hex digits (16 bytes) of the message are the IV
        aes = AES.new(key, AES.MODE_CBC, iv)
        ciphertext = binascii.unhexlify(msg[32:])       # the remaining bytes are an encrypted timestamp
        plaintext = aes.decrypt(ciphertext)
        now = int(time.time()*1000)
        then = int(plaintext)
        diff = abs(now - then)
        return diff < thresh_millis


if __name__ == "__main__":
    mu = MACUtil()
    key = '0123456789abcdef'
    msg = mu.create_mac(key)
    print msg, ' is authentic?=' 'yes' if mu.authenticate_mac(key, msg) else 'no'
