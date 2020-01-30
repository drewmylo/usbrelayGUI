import sys, os, time, ctypes
import tkinter as tk
import pickle
import json

"""
Python GUI by Drew Mylo
"""

__author__ = "Andrew Mylonas"
__date__ = "28/06/2018"

print("5V Relay GUI by Drew Mylo")
print("Running on Python v." + str(sys.version))
print("%d-bit mode" % ({4:32, 8:64}[ctypes.sizeof(ctypes.c_void_p)]))

libpath = "."
relays = {}

if sys.version_info.major >= 3:
    def charpToString(charp):
        return str(ctypes.string_at(charp), 'ascii')


    def stringToCharp(s):
        return bytes(s, "ascii")
else:
    def charpToString(charp):
        return str(ctypes.string_at(charp))


    def stringToCharp(s):
        return bytes(s)  

libfile = {'nt': "usb_relay_device.dll",
           'posix': "usb_relay_device.so",
           'darwin': "usb_relay_device.dylib",
           }[os.name]


devids = []
hdev = None

def exc(msg):  return Exception(msg)


def fail(msg): raise exc(msg)


class L: pass  


setattr(L, "dll", None)


def loadLib():
    if not L.dll:
        print("Loading DLL: %s" % ('/'.join([libpath, libfile])))
        try:
            L.dll = ctypes.CDLL('/'.join([libpath, libfile]))
        except OSError:
            fail("Failed load lib")
    else:
        print("lib already open")


usb_relay_lib_funcs = [
    ("usb_relay_device_enumerate", 'h', None),
    ("usb_relay_device_close", 'e', 'h'),
    ("usb_relay_device_open_with_serial_number", 'h', 'si'),
    ("usb_relay_device_get_num_relays", 'i', 'h'),
    ("usb_relay_device_get_id_string", 's', 'h'),
    ("usb_relay_device_next_dev", 'h', 'h'),
    ("usb_relay_device_get_status_bitmap", 'i', 'h'),
    ("usb_relay_device_open_one_relay_channel", 'e', 'hi'),
    ("usb_relay_device_close_one_relay_channel", 'e', 'hi'),
    ("usb_relay_device_close_all_relay_channel", 'e', None)
]


def getLibFunctions():
    """ Get needed functions and configure types; call lib. init.
    """
    assert L.dll

    libver = L.dll.usb_relay_device_lib_version()
    print("%s version: 0x%X" % (libfile, libver))

    ret = L.dll.usb_relay_init()
    if ret != 0: fail("Failed lib init!")
    ctypemap = {'e': ctypes.c_int, 'h': ctypes.c_void_p, 'p': ctypes.c_void_p,
                'i': ctypes.c_int, 's': ctypes.c_char_p}
    for x in usb_relay_lib_funcs:
        fname, ret, param = x
        try:
            f = getattr(L.dll, fname)
        except Exception:
            fail("Missing lib export:" + fname)

        ps = []
        if param:
            for p in param:
                ps.append(ctypemap[p])
        f.restype = ctypemap[ret]
        f.argtypes = ps
        setattr(L, fname, f)


def openDevById(idstr):
    # Open by known ID:

    h = L.usb_relay_device_open_with_serial_number(stringToCharp(idstr), 5)
    if not h: fail("Cannot open device with id=" + idstr)
    global numch
    numch = L.usb_relay_device_get_num_relays(h)
    if numch <= 0 or numch > 8: fail("Bad number of channels, can be 1-8")
    global hdev
    hdev = h


def closeDev():
    global hdev
    L.usb_relay_device_close(hdev)
    hdev = None


def enumDevs():
    global devids
    devids = []
    enuminfo = L.usb_relay_device_enumerate()
    while enuminfo:
        idstrp = L.usb_relay_device_get_id_string(enuminfo)
        idstr = charpToString(idstrp)
        print(idstr)
        assert len(idstr) == 5
        if not idstr in devids:
            devids.append(idstr)
        else:
            print("Warning! found duplicate ID=" + idstr)
        enuminfo = L.usb_relay_device_next_dev(enuminfo)

    print("Found devices: %d" % len(devids))


def unloadLib():
    global hdev, L
    if hdev: closeDev()
    L.dll.usb_relay_exit()
    L.dll = None
    print("Lib closed")



def fire(serial, timer, chnum):
    openDevById(devids[serial])

    switch_open(chnum, serial)
    time.sleep(timer)
    switch_close(chnum, serial)
    print("<<<Relay flicked for " + str(timer) + "s>>>")
    
    closeDev()
    

def switch_open(chnum, serial):
    openDevById(devids[serial])
    
    
    """ Test one device with handle hdev, 1 or 2 channels """
    global numch, hdev
    if numch <= 0 or numch > 8:
        fail("Bad number of channels on relay device!")



    mask = 0
    ret = L.usb_relay_device_open_one_relay_channel(hdev, chnum)
    if ret != 0: fail("Failed R1 on!")
    mask |= chnum

    st = L.usb_relay_device_get_status_bitmap(hdev)
    if st < 0:  fail("Bad status bitmask")
    print("Relay num ch=%d state=%x" % (numch, st))



def switch_close(chnum, serial):
    openDevById(devids[serial])
    ret = L.usb_relay_device_close_one_relay_channel(hdev, chnum)
    st = L.usb_relay_device_get_status_bitmap(hdev)
    print("Relay num ch=%d state=%x" % (chnum, st))

    

class RelaySwitch(object):
    def __init__(self, ID, time, spacer, status):
        self._ID = ID
        self._time = time
        self.new_time = tk.StringVar()
        self.new_time.set(str(self._time) + 's')
        self._spacer = spacer
        self._status = status
        self._chnum = 0

        self.switch_name = tk.Label(text=get_alias(self))
        self.switch_name.grid(row=(devids.index(self._ID) + 1 + self._spacer))

        self.fire_button = tk.Button(text='Toggle', command=lambda: fire(devids.index(self._ID), self._time, 1))
        self.fire_button.grid(row=(devids.index(self._ID) + 1 + self._spacer), column=6, pady=10)

        self.timer_entry = tk.Entry()
        self.timer_entry.grid(row=(devids.index(self._ID) + 1 + self._spacer), column=1)
        self.timer_entry.insert(0, "0.2")

        self.units_of_time = tk.Spinbox(values=('s', 'ms', 'μs'))
        self.units_of_time.grid(row=(devids.index(self._ID) + 1 + self._spacer), column=2)

        self.timer_set = tk.Button(text="Set", command=lambda: self.set_time((self.timer_entry.get())))
        self.timer_set.grid(row=(devids.index(self._ID) + 1 + self._spacer), column=3)

        self.timer_label = tk.Label(textvariable=self.new_time)
        self.timer_label.grid(row=(devids.index(self._ID) + 1 + self._spacer), column=4)

        self.open_switch = tk.Button(text="Open", command=lambda: switch_open(1, devids.index(self._ID)))
        self.open_switch.grid(row=(devids.index(self._ID) + 1 + self._spacer), column=7)

        self.close_switch = tk.Button(text="Close", command=lambda: switch_close(1, devids.index(self._ID)))
        self.close_switch.grid(row=(devids.index(self._ID) + 1 + self._spacer), column=8)


    def set_ID(self, newId):
        self._ID = newId
    def get_ID(self):
        return self._ID
    def get_chnum(self):
        return self._chnum


    def set_time(self, time):
        x = float(time)
        if self.units_of_time.get() == 'μs':
            x = (float(x) * 10 ** -6)
        elif self.units_of_time.get() == 'ms':
            x = (float(x) * 10 ** -3)
        self.new_time.set(str(x) + 's')
        self._time = float(x)

    def load_time(self, time):
        x = float(time)
        self.new_time.set(str(x) + 's')
        self._time = float(x)

    def get_time(self):
        return self._time


def save_defaults(relays):
    if relays == {}:
        pass
    else:
        with open("defaults.p", "rb") as f:
            defaults = pickle.load(f)
        ids = relays.keys()
        for x in ids:
            defaults[x] = (relays[x].get_time())
        with open("defaults.p", "wb") as f:
            pickle.dump(defaults, f)


def load_defaults(relays):
    if relays == {}:
        pass
    else:
        with open("defaults.p", "rb") as f:
            defaults = pickle.load(f)
        for x in defaults.keys():
            if x in relays.keys():
                relays[x].load_time((defaults[x]))

def get_alias(relay):
    relayCode = relay.get_ID()+str(relay.get_chnum())
    with open("aliases.json", "rb") as f:
        aliases = json.load(f)
           
    if (relayCode) in aliases.keys():
            return (aliases[relayCode])
    else:
        return (relayCode)
    

class TwoChannelRelaySwitch(object):
    def __init__(self, ID, time, chnum):
        self._ID = ID
        self._time = time
        self.new_time = tk.StringVar()
        self.new_time.set(str(self._time) + 's')
        self._chnum = chnum

        self.switch_name = tk.Label(text=get_alias(self))
        self.switch_name.grid(row=(devids.index(self._ID) + 1 + self._chnum))

        self.fire_button = tk.Button(text='Toggle', command=lambda: fire(devids.index(self._ID), self._time, self._chnum))
        self.fire_button.grid(row=(devids.index(self._ID) + 1 + self._chnum), column=6, pady=10)

        self.timer_entry = tk.Entry()
        self.timer_entry.grid(row=(devids.index(self._ID) + 1 + self._chnum), column=1)
        self.timer_entry.insert(0, "0.2")

        self.units_of_time = tk.Spinbox(values=('s', 'ms', 'μs'))
        self.units_of_time.grid(row=(devids.index(self._ID) + 1 + self._chnum), column=2)

        self.timer_set = tk.Button(text="Set", command=lambda: self.set_time(self.timer_entry.get()))
        self.timer_set.grid(row=(devids.index(self._ID) + 1 + self._chnum), column=3)

        self.timer_label = tk.Label(textvariable=self.new_time)
        self.timer_label.grid(row=(devids.index(self._ID) + 1 + self._chnum), column=4)

        self.open_switch = tk.Button(text="Open", command=lambda: switch_open(self._chnum, devids.index(self._ID)))
        self.open_switch.grid(row=(devids.index(self._ID) + 1 + self._chnum), column=7)

        self.close_switch = tk.Button(text="Close", command=lambda: switch_close(self._chnum, devids.index(self._ID)))
        self.close_switch.grid(row=(devids.index(self._ID) + 1 + self._chnum), column=8)

    def set_ID(self, newId):
        self._ID = newId
        
    def get_ID(self):
        return self._ID
        
    def get_chnum(self):
        return self._chnum



    def set_time(self, time):
        x = time
        if self.units_of_time.get() == 'μs':
            x = (float(x) * 10 ** -6)
        elif self.units_of_time.get() == 'ms':
            x = (float(x) * 10 ** -3)
        self.new_time.set(str(x) + 's')
        self._time = float(x)

    def load_time(self, time):
        x = float(time)
        self.new_time.set(str(x) + 's')
        self._time = float(x)

    def get_time(self):
        return self._time
# main
def main():

    loadLib()
    getLibFunctions()
    enumDevs()
    top = tk.Tk()
    top.title("Relay GUI v2")
    top.iconbitmap("hephico.ico")


    menubar = tk.Menu(top)
    filemenu = tk.Menu(menubar, tearoff=0)
    filemenu.add_command(label="Load Defaults", command=lambda: load_defaults(relays))
    filemenu.add_command(label="Save Defaults", command=lambda: save_defaults(relays))
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=top.quit)
    menubar.add_cascade(label="File", menu=filemenu)

    top.config(menu=menubar)

    one = tk.Label(text='Relay', relief=tk.RIDGE)
    one.grid(row=0, column=0, pady=10,)

    one = tk.Label(text='Switch', relief=tk.RIDGE)
    one.grid(row=0, column=6, pady=10)

    one = tk.Label(text='Duration', relief=tk.RIDGE)
    one.grid(row=0, column=1)

    one = tk.Label(text='Units', relief=tk.RIDGE)
    one.grid(row=0, column=2)

    one = tk.Label(text='Set', relief=tk.RIDGE)
    one.grid(row=0, column=3)

    one = tk.Label(text='Current Duration', relief=tk.RIDGE)
    one.grid(row=0, column=4)

    one = tk.Label(text='Open', relief=tk.RIDGE)
    one.grid(row=0, column=7)

    one = tk.Label(text='Close', relief=tk.RIDGE)
    one.grid(row=0, column=8)


    oldnum = 0

    for x in devids:
        openDevById(x)
        if numch == 1:
            relay = RelaySwitch(x, 0.2, oldnum, (L.usb_relay_device_get_status_bitmap(hdev)))
            relays[x] = relay
            
            oldnum = numch
            closeDev()
        elif numch >= 2:
            oldnum = numch
            for y in range(numch):
                relay = TwoChannelRelaySwitch(x, 0.2, (y+1))
                relays[x + str(y + 1)] = relay

            closeDev()
    load_defaults(relays)

    top.mainloop()

if __name__ == "__main__":
    main()



