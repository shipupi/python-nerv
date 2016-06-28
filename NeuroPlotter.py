#coding: latin-1

# http://matplotlib.org/faq/virtualenv_faq.html

import matplotlib.pyplot as plt
import numpy as np

import serial
from struct import *

import sys, select

#import emotiv
import platform
import socket
import gevent

import time
import datetime
import os

from scipy.fftpack import fft

from scipy.signal import firwin, remez, kaiser_atten, kaiser_beta
from scipy.signal import butter, filtfilt, buttord

from sklearn import svm

def psd(y):
    # Number of samplepoints
    N = 128
    # sample spacing
    T = 1.0 / 128.0
    # From 0 to N, N*T, 2 points.
    #x = np.linspace(0.0, 1.0, N)
    #y = 1*np.sin(10.0 * 2.0*np.pi*x) + 9*np.sin(20.0 * 2.0*np.pi*x)


    fs = 128.0
    fso2 = fs/2
    Nd,wn = buttord(wp=[9/fso2,11/fso2], ws=[8/fso2,12/fso2],
       gpass=3.0, gstop=40.0)

    b,a = butter(Nd,wn,'band')

    y = filtfilt(b,a,y)


    yf = fft(y)
    #xf = np.linspace(0.0, 1.0/(2.0*T), N/2)
    #import matplotlib.pyplot as plt
    #plt.plot(xf, 2.0/N * np.abs(yf[0:N/2]))
    #plt.axis((0,60,0,1))
    #plt.grid()
    #plt.show()

    return np.sum(np.abs(yf[0:N/2]))


class Plotter:

    def __init__(self,rangeval,minval,maxval):
        # You probably won't need this if you're embedding things in a tkinter plot...
        plt.ion()

        self.x = []
        self.y = []
        self.z = []

        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111)

        self.line1, = self.ax.plot(self.x,'r', label='X') # Returns a tuple of line objects, thus the comma
        self.line2, = self.ax.plot(self.y,'g', label='Y')
        self.line3, = self.ax.plot(self.z,'b', label='Z')

        self.rangeval = rangeval
        self.ax.axis([0, rangeval, minval, maxval])
        self.plcounter = 0
        self.plotx = []

    def plotdata(self,new_values):
        # is  a valid message struct
        #print new_values

        self.x.append( float(new_values[0]))
        self.y.append( float(new_values[1]))
        self.z.append( float(new_values[2]))

        self.plotx.append( self.plcounter )

        self.line1.set_ydata(self.x)
        self.line2.set_ydata(self.y)
        self.line3.set_ydata(self.z)

        self.line1.set_xdata(self.plotx)
        self.line2.set_xdata(self.plotx)
        self.line3.set_xdata(self.plotx)

        self.fig.canvas.draw()
        plt.pause(0.01)

        self.plcounter = self.plcounter+1

        if self.plcounter > self.rangeval:
          self.plcounter = 0
          self.plotx[:] = []
          self.x[:] = []
          self.y[:] = []
          self.z[:] = []

class Packet():
    def init(self):
        self.O1 = 0
        self.O2 = 0
        self.gyro_x = 0
        self.gyro_y = 0



class OfflineHeadset:
    def __init__(self, subject, label):
        # @TODO Need to parametrize this.
        self.basefilename = '/Users/rramele/Data/%s/Alfa/e.%d.l.%d.dat'
        self.readcounter = 0
        self.running = True
        self.label = label
        self.subject = subject
        self.fileindex = 0
        self.f = None

    def setup(self):
        pass

    def setupfile(self):
        self.datasetfile = self.basefilename % (self.subject,self.fileindex,self.label)
        print self.datasetfile
        if os.path.isfile(self.datasetfile):
            if self.f:
                self.f.close()
            self.f = open(self.datasetfile,'r')
            return True
        else:
            return False

    def nextline(self):
        line = None
        if self.f:
            line = self.f.readline()
        if (not line):
            self.fileindex = self.fileindex + 1

            if self.setupfile():
                return self.nextline()
            else:
                return None
        else:
            return line

    def dequeue(self):
        line = self.nextline()
        if (line):
            data = line.split('\r\n')[0].split(' ')
            packet = Packet()
            packet.O1 = [float(data[7]),0]
            packet.O2 = [float(data[8]),0]
            packet.gyro_x = 0
            packet.gyro_y = 0

            self.readcounter = self.readcounter + 1
            return packet
        else:
            headset.running = False
            return None


    def close(self):
        if (self.f):
            self.f.close()

def process(headset):
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d-%H-%M-%S')
    log = open('data/biosensor-%s.dat' % st, 'w')
    plotter = Plotter(500,4000,5000)
    print ("Starting BioProcessing Thread...")
    readcounter=0
    iterations=0

    N = 128

    window = []
    fullsignal = []
    awindow = None
    afullsignal = None
    features = []


    while headset.running:
        packet = headset.dequeue()
        interations=iterations+1
        if (packet != None):
            datapoint = [packet.O1[0], packet.O2[0]]
            plotter.plotdata( [packet.gyro_x, packet.O2[0], packet.O1[0]])
            log.write( str(packet.gyro_x) + "\t" + str(packet.gyro_y) + "\n" )

            window.append( datapoint )

            if len(window)>=N:
                awindow = np.asarray( window )
                if (afullsignal != None):
                    awindow = awindow - afullsignal.mean(0)

                o1 = psd(awindow[:,0])
                o2 = psd(awindow[:,1])

                print o1, o2

                features.append( [o1, o2] )

                fullsignal.append( window )
                afullsignal = np.asarray( fullsignal )

                # Slide window
                window = window[N/2:N]


            readcounter=readcounter+1

        if (readcounter==0 and iterations>50):
            headset.running = False
        gevent.sleep(0.001)

    log.close()

    return features



def onemore():
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d-%H-%M-%S')
    f = open('sensor.dat', 'w')
    plotter = Plotter(500,4000,5000)
    print ("Starting main thread")
    readcounter=0
    iterations=0

    while headset.running:
        packet = headset.dequeue()
        interations=iterations+1
        if (packet != None):
            datapoint = [packet.O1, packet.O2]
            #print ("Packet:")
            #print (packet.O1)
            plotter.plotdata( [packet.gyro_x, packet.gyro_y, packet.O1[0]])
            f.write( str(packet.gyro_x) + "\t" + str(packet.gyro_y) + "\n" )
            readcounter=readcounter+1

        if (readcounter==0 and iterations>50):
            headset.running = False
        gevent.sleep(0.001)

    f.close()


if __name__ == "__main__":
    while True:
        KeepRunning = True
        headset = None
        while KeepRunning:
            try:
                #headset = emotiv.Emotiv()
                headset = OfflineHeadset('Rodrigo',1)
                gevent.spawn(headset.setup)
                g = gevent.spawn(process, headset)
                gevent.sleep(0.001)

                gevent.joinall([g])
            except KeyboardInterrupt:
                headset.close()
                quit()
            except Exception:
                pass

            if (headset):
                headset.close()
                if (headset.readcounter==0):
                    print ("Restarting headset object...")
                    continue
                else:
                    quit()
