#!/usr/bin/python
"""
Created on Thu Dec  1 15:41:13 2016

@author: pavla kratochvilova
"""
# Setup Python logging --------------------------------------------------------
import logging
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Imports----------------------------------------------------------------------
import common
from argparse import ArgumentParser
from time import sleep
import threading
import pika
# Constants -------------------------------------------------------------------
___NAME = 'Battleship Game Client'
___VER = '0.1.0.0'
___DESC = 'Battleship Game Client'
___BUILT = '2016-11-10'
# Classes ---------------------------------------------------------------------
class Game():
    pass

class Clients():
    '''Process client connections.
    '''
    def __init__(self, channel, server_name):
        '''Set a set of client usernames, communication channel, and consuming.
        @param channel: pika connection channel
        @param server_name: name of server
        '''
        # Set of client usernames
        self.client_set = set()
        
        # Communication
        self.channel = channel
        self.connect_queue = channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.connect_queue,
                                routing_key=server_name)
        self.channel.basic_consume(self.process_client,
                                   queue=self.connect_queue,
                                   no_ack=True)
    
    def process_client(self, ch, method, properties, body):
        '''Process client request.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode        
        '''
        LOG.debug('Received message: %s' % body)
        msg_parts = body.split(common.MSG_SEPARATOR, 1)
        
        # Connect request
        if msg_parts[0] == common.REQ_CONNECT:
            if msg_parts[1] in self.client_set:
                response = common.RSP_USERNAME_TAKEN
            else:
                self.client_set.add(msg_parts[1])
                response = common.RSP_OK
        
        # Disconnect request
        elif msg_parts[0] == common.REQ_DISCONNECT:
            try:
                self.client_set.remove(msg_parts[1])
                response = common.RSP_OK
            except KeyError:
                response = common.RSP_CLIENT_NOT_CONNECTED
        else:
            response = common.RSP_INVALID_REQUEST
        
        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s' % response)

# Functions -------------------------------------------------------------------
def __info():
    return '%s version %s (%s)' % (___NAME, ___VER, ___BUILT)

def publish_advertisements(server_on, channel, message):
    while server_on[0]:
        channel.basic_publish(exchange='direct_logs', 
                              routing_key='server_advert', 
                              body=message)
        sleep(5)

def stop_server(channel, message):
    channel.basic_publish(exchange='direct_logs', 
                          routing_key='server_stop', 
                          body=message)

# Main function ---------------------------------------------------------------
if __name__ == '__main__':
    # Parsing arguments
    parser = ArgumentParser()
    parser.add_argument('-H','--host', \
                        help='Addres of the RabitMQ server, '\
                        'defaults to %s' % common.DEFAULT_SERVER_INET_ADDR, \
                        default=common.DEFAULT_SERVER_INET_ADDR)
    parser.add_argument('-p','--port', \
                        help='Port of the RabitMQ server, '\
                        'defaults to %d' % common.DEFAULT_SERVER_PORT, \
                        default=common.DEFAULT_SERVER_PORT)
    parser.add_argument('-n','--name', \
                        help='Server name.',\
                        required=True)
    args = parser.parse_args()

    # Connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=args.host, port=args.port))
    channel = connection.channel()
    channel.exchange_declare(exchange='direct_logs', type='direct')

    # Client connections
    clients = Clients(channel, args.name)
    
    # Server advertisements
    server_on = [True]
    t = threading.Thread(target=publish_advertisements,
                         args=(server_on, channel, args.name))
    t.setDaemon(True)
    t.start()
    LOG.debug('Started advertising.')
    
    # Dict of games
    games = {}
    
    try:
        while True:
            channel.start_consuming()
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating server ...')
    
    server_on[0] = False
    stop_server(channel, args.name)
    LOG.debug('Stopped advertising.')
