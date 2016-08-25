import numpy as np
import math
import os
import pandas as pd
import datetime
import meta2_interface as meta2
import getcalibration

def float2hex(f):
    if f==0:
        return [0,0,0,0]
    if f>0:
        sign = 0
    else:
        sign = 1
    f = abs(f)
    exp = math.floor(math.log10(f)/math.log10(2))
    remainder = int(8388608*((f/math.pow(2,exp))-1))
    upperexp = int(((exp+127)/2.))
    lowerexp = int((exp+127)&1)
    return [remainder&255,(remainder>>8)&255,
            (lowerexp*128)+((remainder>>16)&127),
            (sign*128)+upperexp]

def floatbit(f):
    return f-int(f)

def integer2hex(i):
    i = int(i)
    return [i&255,(i>>8)&255,(i>>16)&255,i>>24]
    

date_1970 = pd.Timestamp('1970')
RAW = '/cluster/data/raw/'
EXT = '/home/ahk114/extended/'
PROC = '/home/ahk114/testdata/'

def satt_stof_proc(sc,date,versions=['B','K','A'],RAW=RAW,PROC=PROC):
    '''
    eg.
    sattfile=RAW+'2016/01/'+'C'+'1'+'_'+'160122'+'_'+'B'+'.SATT' #Spacecraft Attitude and Spin Rates
    stoffile=RAW+'2016/01/'+'C'+'1'+'_'+'160122'+'_'+'B'+'.STOF'
    procfile=PROC+'2016/01/'+'C'+'1'+'_'+'160122'+'_'+'B'+'.EXT.GSE' #Where the data goes - into the reference folder!
    '''
    for version in versions:
        sattfile=RAW+date.strftime('%Y/%m/')+'C'+format(sc,'1d')+'_'+ \
                    date.strftime('%y%m%d')+'_'+version.upper()+'.SATT'

        stoffile=RAW+date.strftime('%Y/%m/')+'C'+format(sc,'1d')+'_'+ \
                    date.strftime('%y%m%d')+'_'+version.upper()+'.STOF'
        if os.path.isfile(stoffile) and os.path.isfile(sattfile):
            break     
    procfile=PROC+date.strftime('%Y/%m/')+'C'+format(sc,'1d')+'_'+ \
                date.strftime('%y%m%d')+'_'+version.upper()+'.EXT.GSE'
    if not os.path.isdir(PROC+date.strftime('%Y/%m/')):
        os.makedirs(PROC+date.strftime('%Y/%m/'))
    if os.path.isfile(stoffile) and os.path.isfile(sattfile) and \
    os.path.isdir(PROC+date.strftime('%Y/%m/')):
        return sattfile,stoffile,procfile
    else:
        return False,False,False

def write_data(sc,ext_data,OUT=PROC): 
    k2   = np.pi / 4
    initial_date = ext_data['time'].iloc[0].date()
    offsetx,offsety,offsetz,gainx,gainy,gainz = \
                    getcalibration.getcal(sc,initial_date,calibration='CAA')
    '''
    for the calibration the IB sensor and ADC 0 info will be read by default
    '''
    sattfile,stoffile,procfile = satt_stof_proc(sc,initial_date,PROC=OUT)
    tmp = '/home/ahk114/testdata/ExtProcRaw_123'
    tmp2 = '/home/ahk114/testdata/ExtProcDecoded_123'
    datahandle = open(tmp,'wb')
    for key,row in ext_data.iterrows():
        time = (row['time']-date_1970)/pd.Timedelta(1,'s')
        r_range = row['range']
        x = row['x']*gainx[0,r_range] - offsetx[0,r_range]
        y = row['y']*k2*gainy[0,r_range] - offsety[0,r_range]
        z = row['z']*k2*gainz[0,r_range] - offsetz[0,r_range]
        hexbx = float2hex(x)
        hexby = float2hex(y)
        hexbz = float2hex(z)
        time1 = integer2hex(time)
        time2 = integer2hex(floatbit(time)*1e9)
        data = [(r_range<<4)+14,
        16,
        128+(1&7),
        (((sc-1)<<6)+1),
        time1[0],time1[1],time1[2],time1[3],
        time2[0],time2[1],time2[2],time2[3]]  
        data.extend(hexbx)
        data.extend(hexby)
        data.extend(hexbz)
        data.extend([0,0,0,0,0,0,0,0])
        for content in data:
            datahandle.write(chr(content))	
        if row['time'].date()-initial_date == pd.Timedelta(1,'D'):
            '''
            We are into the next day. so break open a new file!
            Also process what we had from the first day.
            '''
            datahandle.close()
            cmd = ('FGMPATH=/cluster/operations/calibration/default ; '
                    'export FGMPATH ; cat '+tmp+' | '
                    '/cluster/operations/software/dp/bin/fgmhrt -s gse -a '+sattfile+' | ' 
                    '/cluster/operations/software/dp/bin/fgmpos -p '+stoffile+' | '
                    '/cluster/operations/software/dp/bin/igmvec -o '+tmp2+' 2>/dev/null ; '
                    'cat '+tmp2+' >> '+procfile+' ;')	
                    #append here, not copy (ie. overwrite)
            os.system(cmd)    
            datahandle = open(tmp,'wb')
            sattfile,stoffile,procfile = satt_stof_proc(sc,row['time'].date(),
                                                        PROC=OUT)
            offsetx,offsety,offsetz,gainx,gainy,gainz = \
                getcalibration.getcal(sc,row['time'].date(),calibration='CAA')                                                        
    		
    datahandle.close()
    cmd = ('FGMPATH=/cluster/operations/calibration/default ; '
            'export FGMPATH ; cat '+tmp+' | '
            '/cluster/operations/software/dp/bin/fgmhrt -s gse -a '+sattfile+' | ' 
            '/cluster/operations/software/dp/bin/fgmpos -p '+stoffile+' | '
            '/cluster/operations/software/dp/bin/igmvec -o '+tmp2+' 2>/dev/null ; '
            'cp '+tmp2+' '+procfile+' ;')	
    os.system(cmd)