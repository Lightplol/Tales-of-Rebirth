import sys
import os
import json
import struct
import re
import subprocess
import shutil
import string

types = {'dummy' : 99, 'scpk': 133}
tags = {0x5: 'color', 0xB: 'name'}

use_compression = True

pointer_begin = 0xD76B0
pointer_end   = 0xE60C8

high_bits = 0xFFFFFFC0
low_bits = 0x3F

com_tag = r'(<\w+:[0-9A-F]{8}>)'
hex_tag = r'(\{[0-9A-F]{2}\})'

printable = ''.join((string.digits,string.ascii_letters,string.punctuation,' '))
    
def mkdir(name):
    try:
        os.mkdir(name)
    except:
        pass
    
def get_pointers():
    f = open("SLPS_254.50", 'rb')
    f.seek(pointer_begin, 0)
    pointers = []

    while f.tell() < pointer_end:
        p = struct.unpack('<L', f.read(4))[0]
        pointers.append(p)

    f.close()
    return pointers

def get_ext(data):
    ext = 'bin'
    if data[:4].isalpha():
        ext = data[:4].decode('ascii')
        if ext == 'VAGp':
            ext = 'vag'
    elif data[:3].isalpha():
        ext = data[:3].decode('ascii')
        if ext == 'MIG':
            ext = 'GIM'
    elif data[0:4] == b'\x89PNG':
        ext = 'png'
    elif data[0:1].isalpha() and data[0x10:0x11] == b'.':
        ext = 'arc'
    elif data[0:4] == b'MIG.':
        ext = 'GIM'
    return ext

def compress_comptoe(name, ctype=1):
    if ctype == 1:
        subprocess.run(['comptoe', '-c1', name, name + '.c'])
    else:
        subprocess.run(['comptoe', '-c3', name, name + '.c'])

def decompress_comptoe(name):
    subprocess.run(['comptoe', '-d', name, name + '.d'])

def decompress_folder(name):
    for f in os.listdir(name):
        if f.endswith('.'):
            continue
        subprocess.run(['comptoe', '-d', name + f, name + f + '.d'])

def move_sced():
    mkdir('SCED')
    sced_dir = os.getcwd() + '/sced/'
    
    for folder in os.listdir('scpk'):
        if not os.path.isdir('scpk/' + folder):
            continue
        for sce in os.listdir('scpk/' + folder):
            if sce.endswith('.sced'):
                f = sce
                break
        new_name = '%s_%s.sced' % (folder, f.split('.')[0])
        shutil.copy(os.path.join('scpk',folder,f), sced_dir + new_name)
        print (new_name)

def replace_sced():
    for name in os.listdir('sced_new/'):
        scpk_path = os.path.join('scpk/', name[:5], name[6:])
        shutil.copy(os.path.join('sced_new/', name), scpk_path)
        print (name)
    
def extract_dat():
    f = open('DAT.bin', 'rb')
    mkdir('DAT')
    json_file = open('DAT.json', 'w')
    json_data = {}
    pointers = get_pointers()
    
    for i in range(len(pointers) - 1):
        remainder = pointers[i] & low_bits
        start = pointers[i] & high_bits
        end = (pointers[i+1] & high_bits) - remainder
        f.seek(start, 0)
        size = (end - start)
        if size == 0:
            json_data[i] = types['dummy']
            continue
        data = f.read(size)
        extension = 'bin'
        if data[:4] == b'SCPK':
            extension = 'scpk'
            json_data[i] = types['scpk']
        else:
            json_data[i] = data[0]
        o = open('DAT/' + '%05d.%s' % (i, extension), 'wb')
        o.write(data)
        o.close()
        print (i)

    json.dump(json_data, json_file, indent=4)
    f.close()

def pack_dat():
    sectors = [0]
    remainders = []
    buffer = 0
    json_file = open('dat.json', 'r')
    json_data = json.load(json_file)
    json_file.close()
    o = open('NEW_DAT.BIN', 'wb')
    
    for k, v in json_data.items():
        size = 0
        remainder = 0
        if v != types["dummy"]:
            extension = 'bin'
            if v == types['scpk']:
                extension = 'scpk'
            f = open('dat/%05d.%s' % (int(k), extension), 'rb')
            o.write(f.read())
            size = os.path.getsize('dat/%05d.%s' % (int(k), extension))
            remainder = 0x40 - (size % 0x40)
            if remainder == 0x40:
                remainder = 0
            o.write(b'\x00' * remainder)
            f.close()
        remainders.append(remainder)
        buffer += (size + remainder)
        sectors.append(buffer)
        print (k)

    u = open('new_SLPS_254.50', 'r+b')
    u.seek(pointer_begin)
    
    for i in range(len(sectors) - 1):
        u.write(struct.pack('<L', sectors[i] + remainders[i]))
        
    o.close()
    u.close()

def extract_scpk():
    mkdir('SCPK')
    json_file = open('SCPK.json', 'w')
    json_data = {}
    
    for file in os.listdir('DAT'):
        if not file.endswith('scpk'):
            continue
        f = open('DAT/%s' % file, 'rb')
        header = f.read(4)
        if header != b'SCPK':
            f.close()
            continue
        mkdir('scpk/%s' % file.split('.')[0])
        index = file.split('.')[0]
        json_data[index] = {}
        f.read(4)
        files = struct.unpack('<L', f.read(4))[0]
        f.read(4)
        sizes = []
        for i in range(files):
            sizes.append(struct.unpack('<L', f.read(4))[0])
        for i in range(files):
            data = f.read(sizes[i])
            ext = 'bin'
            if len(data) >= 0xA:
                if data[0xA] == 0x54:
                    ext = 'sced'
            fname = 'scpk/%s/%02d.%s' % (file.split('.')[0], i, ext)
            o = open(fname, 'wb')
            json_data[index][i] = data[0]
            o.write(data)
            o.close()
            if use_compression:
                if ext == 'sced':
                    decompress_comptoe(fname)
                    os.remove(fname)
                    os.rename(fname + '.d', fname)

        f.close()
        print (file)
        
    json.dump(json_data, json_file, indent=4)

def pack_scpk():
    mkdir('SCPK_PACKED')
    json_file = open('SCPK.json', 'r')
    json_data = json.load(json_file)
    json_file.close()
    
    for folder in os.listdir('scpk/'):
        if os.path.isdir('scpk/' + folder):
            sizes = []
            o = open('scpk_packed/%s.SCPK' % folder, 'wb')
            data = bytearray()
            listdir = os.listdir('scpk/' + folder)
            for file in listdir:
                read = bytearray()
                index = str(int(file.split('.')[0]))
                fname = 'scpk/%s/%s' % (folder, file)
                f = open(fname, 'rb')
                ctype = json_data[folder][index]
                if file.endswith('sced'):
                    if ctype != 0:
                        if use_compression:
                            compress_comptoe(fname, ctype)
                            comp = open(fname + '.c', 'rb')
                            read = comp.read()
                            comp.close()
                            os.remove(fname + '.c')
                        else:
                            read = f.read()
                    else:
                        read = f.read()
                else:
                    read = f.read()
                data += read
                sizes.append(len(read))
                f.close()
                
            o.write(b'\x53\x43\x50\x4B\x01\x00\x07\x00')
            o.write(struct.pack('<L', len(sizes)))
            o.write(b'\x00' * 4)
            
            for i in range(len(sizes)):
                o.write(struct.pack('<L', sizes[i]))
                
            o.write(data)
            o.close()
            
        print (folder)

def extract_sced():
    mkdir('TXT')
    json_file = open('TBL.json', 'r')
    json_data = json.load(json_file)
    json_file.close()

    sced_file = open('SCED.json', 'w')
    sced_data = {}
    
    for name in os.listdir('sced/'):
        f = open('sced/' + name, 'rb')
        header = f.read(8)
        if header != b'THEIRSCE':
            continue
        o = open('txt/' + name + '.txt', 'w', encoding='utf-8')
        sced_data[name] = []
        pointer_block = struct.unpack('<L', f.read(4))[0]
        text_block = struct.unpack('<L', f.read(4))[0]
        fsize = os.path.getsize('sced/' + name)
        f8_addr = []
        text_pointers = []
        f.seek(pointer_block, 0)
        prev = 0
        
        while f.tell() < text_block:
            b = f.read(1)
            if b == b'\xF8':
                addr = struct.unpack('<H', f.read(2))[0]
                if (addr < fsize - text_block) and (addr > 0) and (addr > prev):
                    sced_data[name].append(f.tell() - 2)
                    text_pointers.append(addr)
                    prev = addr
        
        for i in range(len(text_pointers)):
            f.seek(text_block + text_pointers[i], 0)
            b = f.read(1)
            while b != b'\x00':
                b = ord(b)
                if (b >= 0x99 and b <= 0x9F) or (b >= 0xE0 and b <= 0xEB):
                    c = (b << 8) + ord(f.read(1))
                    o.write(json_data[str(c)])
                elif b == 0x1:
                    o.write('\n')
                elif b in (0x3, 0x4, 0x5, 0x6, 0x7, 0x8, 0x9, 0xB, 0xE, 0xF):
                    b2 = struct.unpack('<L', f.read(4))[0]
                    #if b in tags:
                    #    o.write('<%s:%08X>' % (tags[b], b2))
                    #else:
                    o.write('<%02X:%08X>' % (b, b2))
                elif chr(b) in printable:
                    o.write(chr(b))
                elif b >= 0xA1 and b < 0xE0:
                    o.write(struct.pack('B', b).decode('cp932'))
                elif b in (0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19):
                    o.write('{%02X}' % b)
                    next_b = b''
                    while next_b != b'\x80':
                        next_b = f.read(1)
                        o.write('{%02X}' % ord(next_b))
                else:
                    o.write('{%02X}' % b)
                b = f.read(1)
            o.write('\n-----------------------\n')
        print (name)
        f.close()
        o.close()

    json.dump(sced_data, sced_file, indent=4)

def insert_sced():
    json_file = open('TBL.json', 'r')
    sced_json = open('SCED.json', 'r')
    table = json.load(json_file)
    sced_data = json.load(sced_json)
    json_file.close()
    sced_json.close()
    
    itable = dict([[i,struct.pack('>H', int(j))] for j,i in table.items()])
    itags = dict([[i,j] for j,i in tags.items()])
    
    mkdir('SCED_NEW/')

    for name in os.listdir('txt'):
        f = open('txt/' + name, 'r', encoding='utf8')
        name = name[:-4]
        sced = open('sced/' + name, 'rb')
        o = open('sced_new/' + name, 'wb')

        txts = []
        sizes = []
        txt = bytearray()

        for line in f:
            line = line.strip('\x0A')
            if line == '-----------------------':
                if len(line) == 0:
                    txts.append(b'\x00')
                else:
                    txts.append(txt[:-1] + b'\x00')
                sizes.append(len(txt))
                txt = bytearray()
            else:
                string_hex = re.split(hex_tag, line)
                for s in string_hex:
                    if s:
                        if re.match(hex_tag, s):
                            txt += (struct.pack('B', int(s[1:3], 16)))
                        else:
                            s_com = re.split(com_tag, s)
                            for c in s_com:
                                if c:
                                    if re.match(com_tag, c):
                                        split = c.split(':') 
                                        if split[0][1:] in itags.keys():
                                            txt += (struct.pack('B', itags[split[0][1:]]))
                                        else:
                                            txt += (struct.pack('B', int(split[0][1:], 16)))
                                        txt += (struct.pack('<I', int(split[1][:8], 16)))
                                    else:
                                        for c2 in c:
                                            if c2 in itable.keys():
                                                txt += itable[c2]
                                            else:
                                                txt += c2.encode('cp932')
                txt += (b'\x01')
                
        f.close()
        
        sced.seek(0xC, 0)
        pointer_block = struct.unpack('<L', sced.read(4))[0]
        sced.seek(0, 0)
        header = sced.read(pointer_block)
        o.write(header + b'\x00')
        sced.close()

        pos = 1
        for i in range(len(txts)):
            o.seek(sced_data[name][i], 0)
            o.write(struct.pack('<H', pos))
            pos += sizes[i]

        o.seek(pointer_block + 1, 0)
        
        for t in txts:
            o.write(t)
        o.close()

        print (name)
            
if __name__ == '__main__':
    if sys.argv[1] == '1':
        extract_dat()
    elif sys.argv[1] == '2':
        pack_dat()
    elif sys.argv[1] == '3':
        extract_scpk()
    elif sys.argv[1] == '4':
        pack_scpk()
    elif sys.argv[1] == '5':
        move_sced()
    elif sys.argv[1] == '6':
        extract_sced()
    elif sys.argv[1] == '7':
        insert_sced()
    elif sys.argv[1] == '8':
        replace_sced()
    elif sys.argv[1] == '9':
        decompress_folder('compressed/')
    else:
        sys.exit(1)
