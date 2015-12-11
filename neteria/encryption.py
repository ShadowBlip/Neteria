#!/usr/bin/python
"""The encryption module is used to encrypt and decrypt messages using the
python-rsa package.

You can run an example by running the following from the command line:
`python -m neteria.encryption`"""

import json
import binascii
import textwrap

try:
    import rsa
except:
    rsa = False


class Encryption():

    """Handles encrypting and decrypting messages using RSA public key/private
    key authentication.

    Args:
      key_length (int): The length of the encryption key in bytes. All messages
        will be this size, so larger keys means larger packets. Defaults to 512

    """

    def __init__(self, key_length=512):

        # Set the key length
        self.key_length = key_length

        # Generate a public key/private key pair
        self.public_key, self.private_key = rsa.newkeys(self.key_length)

        # To send the public key, just send the values of "n" and "e", then we
        # can construct a new PublicKey object on the other side.
        self.n = self.public_key["n"]
        self.e = self.public_key["e"]


    def encrypt(self, message, public_key):
        """Encrypts a string using a given rsa.PublicKey object. If the message
        is larger than the key, it will split it up into a list and encrypt
        each line in the list.

        Args:
          message (string): The string to encrypt.
          public_key (rsa.PublicKey): The key object used to encrypt the
            message. Only the paired private key can decrypt it.

        Returns:
        A json string of the list of encrypted lines of the message.

        """
        # Get the maximum message length based on the key
        max_str_len = rsa.common.byte_size(public_key.n) - 11

        # If the message is longer than the key size, split it into a list to
        # be encrypted
        if len(message) > max_str_len:
            message = textwrap.wrap(message, width=max_str_len)
        else:
            message = [message]

        # Create a list for the encrypted message to send
        enc_msg = []

        # If we have a long message, loop through and encrypt each part of the
        # string
        for line in message:

            # Encrypt the line in the message into a bytestring
            enc_line = rsa.encrypt(line, public_key)

            # Convert the encrypted bytestring into ASCII, so we can send it
            # over the network
            enc_line_converted = binascii.b2a_base64(enc_line)

            enc_msg.append(enc_line_converted)

        # Serialize the encrypted message again with json
        enc_msg = json.dumps(enc_msg)

        # Return the list of encrypted strings
        return enc_msg


    def decrypt(self, message):
        """Decrypts a string using our own private key object.

        Args:
          message (string): The string of the message to decrypt.

        Returns:
        The unencrypted string.

        """

        # Unserialize the encrypted message
        message = json.loads(message)

        # Set up a list for the unencrypted lines of the message
        unencrypted_msg = []

        for line in message:

            # Convert from ascii back to bytestring
            enc_line = binascii.a2b_base64(line)

            # Decrypt the line using our private key
            unencrypted_line = rsa.decrypt(enc_line, self.private_key)

            unencrypted_msg.append(unencrypted_line)

        # Convert the message from a list back into a string
        unencrypted_msg = "".join(unencrypted_msg)

        return unencrypted_msg


# Run an example if we execute standalone
if __name__ == '__main__':

    import zlib

    message = "hello asdmkasd" * 50
    # message = "hi"
    print("Plain text:", message)
    message = zlib.compress(message)
    message = binascii.b2a_base64(message)
    print("")
    print("Compressed message:", message)
    print("")

    enc = Encryption()

    msg = enc.encrypt(message, enc.public_key)
    decrypted_msg = enc.decrypt(msg)
    print("Encryped message:", msg)
    print("")
    print("Decrypted message:", decrypted_msg)
    decrypted_msg = binascii.a2b_base64(decrypted_msg)
    uncompressed_msg = zlib.decompress(decrypted_msg)
    print("")
    print("Decompressed message:", uncompressed_msg)
