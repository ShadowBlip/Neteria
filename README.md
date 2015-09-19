## Installing

You can install Neteria by running the following command:

`sudo python setup.py install`

or

`sudo pip install -e .`


## Enabling Logging

Neteria uses the python logging module for all log messages. By default,
Neteria will not print any log messages. Right now there are 3 available
loggers that you can use:

- neteria.core
- neteria.client
- neteria.server

To enable Neteria logging in your application, add the following code into your
app:

```python
import logging
import sys
logger = logging.getLogger('neteria.server')
logger.setLevel(logging.DEBUG)
log_hdlr = logging.StreamHandler(sys.stdout)
log_hdlr.setLevel(logging.DEBUG)
logger.addHandler(log_hdlr)```