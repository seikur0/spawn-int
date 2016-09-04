import os
import json
import re
from operator import itemgetter, attrgetter
import math

list_sids = []
list_spoints = []

workdir = os.path.dirname(os.path.realpath(__file__))

SPAWN_UNDEF = -1
SPAWN_DEF = 1
SPAWN_1x15 = 101
SPAWN_1x30 = 102
SPAWN_1x45 = 103
SPAWN_1x60 = 104
SPAWN_2x15 = 201  # 2x15
SPAWN_1x60h2 = 202
SPAWN_1x60h3 = 203
SPAWN_1x60h23 = 204
VSPAWN = 2222

hour_ms = 3600000
halfh_ms = 1800000
q_ms = 900000
q3_ms = 2700000

class spawnpoint:
    def __init__(self, lat, lng, spawnid):
        self.lat = lat
        self.lng = lng
        self.spawnid = spawnid

        self.type = SPAWN_UNDEF
        self.pauses = -1
        self.spawntime = -1
        self.pausetime = -1

        self.eid_changes = [[0,hour_ms]]
        self.quarter_base = []
        self.quarter_sights = []
        self.quarter_bools = []
        self.sightings = []

def spawnstats(scandata):
    types = [SPAWN_1x15, SPAWN_1x30, SPAWN_1x45, SPAWN_1x60, SPAWN_2x15,SPAWN_1x60h2, SPAWN_1x60h3, SPAWN_1x60h23, SPAWN_UNDEF]
    typestrs = ['1x15', '1x30', '1x45', '1x60', '2x15','1x60h2', '1x60h3', '1x60h23', 'UNDEF']
    typecount = [0, 0, 0, 0, 0, 0, 0, 0, 0]
    tallcount = len(scandata['spawns'])

    for spawn in scandata['spawns']:
        for t in range(0, len(types)):
            if spawn['type'] == types[t]:
                typecount[t] += 1

    print('[+] Spawn point count: {}'.format(tallcount))
    for t in range(0, len(types)):
        print('[+] Type: {}, Count: {}, Percentage: {}%'.format(typestrs[t], typecount[t], round(100.0 * typecount[t] / tallcount, 2)))
    print('\n')

def writefile(file):
    scandata = {'parameters': [], 'emptylocs': [], 'spawns': [], 'stops': [], 'gyms': []}
    for spoint in list_spoints:
        scandata['spawns'].append({'type': spoint.type, 'id': spoint.spawnid, 'lat': spoint.lat, 'lng': spoint.lng, 'spawntime': spoint.spawntime / 60000.0, 'phasetime': 60, 'pauses': spoint.pauses, 'pausetime': spoint.pausetime / 60000.0})

    spawnstats(scandata)

    dir = os.path.dirname(file)
    if not os.path.exists(dir):
        os.makedirs(dir)
    print('writing output file: {}'.format(file))
    f = open(file, 'w', 0)
    json.dump(scandata, f, indent=1, separators=(',', ': '))
    f.close()

def readfile(file):
    svars = ['eid','time','tth','sid','lat','lng','stime']
    inds = dict.fromkeys(svars)

    print('loading input file: {}'.format(file))
    f = open(file, 'r')
    line = f.readline().rstrip('\n')
    header = str.split(line, '\t')
    inds['eid'] = header.index('encounterID')
    inds['time'] = header.index('Time')
    inds['tth'] = header.index('Time2Hidden')
    inds['sid'] = header.index('SpawnID')
    inds['lat'] = header.index('lat')
    inds['lng'] = header.index('lng')
    inds['stime'] = header.index('spawnTime')

    line = f.readline().rstrip('\n')
    while line is not '':
        linedata = str.split(line, '\t')
        sid = int(linedata[inds['sid']])
        if sid < 8796093022208:
            try:
                spoint = list_spoints[list_sids.index(sid)]
            except ValueError:
                list_sids.append(sid)
                spoint = spawnpoint(float(linedata[inds['lat']]),float(linedata[inds['lng']]),sid)
                list_spoints.append(spoint)

            eid, time, tth, stime = int(linedata[inds['eid']]), int(float(linedata[inds['time']]) * 1000), int(float(linedata[inds['tth']]) * 1000), int(float(linedata[inds['stime']]) * 1000)
            if stime > time:
                tth = -1

            spoint.sightings.append({'eid': eid, 'time': time, 'tth': tth})
            if 0 < tth <= hour_ms:
                divide15 = int(math.ceil(float(tth - 2) / q_ms))
                spoint.sightings.append({'eid': eid, 'time': time+tth-q_ms*divide15+1000, 'tth': q_ms*divide15-1000})
                for s in range(0,divide15):
                    spoint.sightings.append({'eid': eid, 'time': time + s*q_ms, 'tth': tth - s*q_ms})
                spoint.sightings.append({'eid': eid, 'time': time + tth - 1000, 'tth': 1000})

        line = f.readline().rstrip('\n')
    f.close()

debid = 4928241454633

err_t = 10
err_tth = 1
err_c = 2*(err_t+err_tth)


def getinfo():
    for spoint in list_spoints:
        spoint.sightings = sorted(spoint.sightings, key=itemgetter('time'))
        ####################################################### extracts the sightings within the hour and the quarter base (good)
        for s in range(0,len(spoint.sightings)):
            spoint.quarter_sights.append(spoint.sightings[s]['time'] % hour_ms)
            if 0 < spoint.sightings[s]['tth'] <= hour_ms:
                qtime = (spoint.sightings[s]['time'] + spoint.sightings[s]['tth'] - q_ms) % hour_ms
                isnew = True
                for n in range(0,len(spoint.quarter_base)):
                    qdiff = (qtime-spoint.quarter_base[n]) % hour_ms
                    if qdiff < (err_c+1): # max observed qdiff is 20
                        spoint.quarter_base[n] = qtime
                        isnew = False
                    elif qdiff > hour_ms-(err_c+1):
                        isnew = False
                if isnew:
                    spoint.quarter_base.append(qtime)

        ####################################################### extracts the number of pauses (good)
        if len(spoint.quarter_base) > 2:
            print('error 1')
            spoint.type = SPAWN_UNDEF
            continue
        elif len(spoint.quarter_base) == 2:
            if halfh_ms - (2*err_c + 1) < (spoint.quarter_base[1]-spoint.quarter_base[0]) % hour_ms < halfh_ms + (2*err_c + 1):
                spoint.pauses = 2
                spoint.type = SPAWN_2x15
                spoint.pausetime = 15 * 60000
            else:
                print('error 2')
                spoint.type = SPAWN_UNDEF
                continue
        elif len(spoint.quarter_base) == 1:
            spoint.pauses = 1
        elif len(spoint.quarter_base) == 0:
            spoint.pauses = 0

        if debid == spoint.spawnid:
            print('')
            print('debug')
            print(spoint.pauses)
            print(spoint.quarter_base)
            print('')

        ####################################################### extracts the eid change sighting pairs, error included (good)
        for s in range(0,len(spoint.sightings)):
            if s > 0:
                pre_eid = spoint.sightings[s-1]['eid']
                post_eid = spoint.sightings[s]['eid']
                pre_time = spoint.sightings[s-1]['time'] - err_t
                post_time = spoint.sightings[s]['time'] + err_t
                if not pre_eid == post_eid and post_time-pre_time <= hour_ms:
                    pre_time = pre_time % hour_ms
                    post_time = post_time % hour_ms
                    new_eid_changes = []
                    if post_time > pre_time:
                        for c in range(0, len(spoint.eid_changes)):
                            new_eid_changes.append([max(spoint.eid_changes[c][0],pre_time),min(spoint.eid_changes[c][1],post_time)])
                    else:
                        for c in range(0, len(spoint.eid_changes)):
                            new_eid_changes.append([max(spoint.eid_changes[c][0],pre_time-hour_ms),min(spoint.eid_changes[c][1],post_time)])
                        for c in range(0, len(spoint.eid_changes)):
                            new_eid_changes.append([max(spoint.eid_changes[c][0],pre_time),min(spoint.eid_changes[c][1],post_time+hour_ms)])

                    c = 0
                    while c <  len(new_eid_changes):
                        if new_eid_changes[c][0] >= new_eid_changes[c][1]:
                            new_eid_changes.pop(c)
                        else:
                            c = c + 1
                    spoint.eid_changes = new_eid_changes

        if debid == spoint.spawnid:
            print(spoint.eid_changes)
            print('')

        ####################################################### reduces the eid change sighting pairs based on possible spawn times (based on quarter base) (good)
        if len(spoint.eid_changes) > 1 and spoint.pauses > 0:
            qbase15 = spoint.quarter_base[0] % q_ms
            qbases15 = [qbase15, qbase15+q_ms, qbase15+halfh_ms,qbase15+q3_ms]

            c = 0
            while c < len(spoint.eid_changes):
                possible = False
                for qbase15 in qbases15:
                    if spoint.eid_changes[c][0] - (err_c+1) < qbase15 < spoint.eid_changes[c][1] + (err_c+1):
                        possible = True
                if possible:
                    c = c + 1
                else:
                    spoint.eid_changes.pop(c)

        ####################################################### determines which of the two qurterbases for 2x15 spawns is the spawntime (good)
        if spoint.pauses == 2:
            possible = [False,False]
            for entry in spoint.eid_changes:
                for q in range(0,2):
                    if entry[0] - (err_c+1) < spoint.quarter_base[q] < entry[1] + (err_c+1):
                        possible[q] = True
            if possible[0] ^ possible[1]:
                if possible[0]:
                    spoint.quarter_base = spoint.quarter_base[0]
                else:
                    spoint.quarter_base = spoint.quarter_base[1]
                spoint.spawntime = spoint.quarter_base
            else:
                print('error 3')
                spoint.type = SPAWN_UNDEF
                spoint.pauses = -1
                continue

        ####################################################### joins a possible border eid change sighting pair (good)
        entries = len(spoint.eid_changes)
        if entries > 1 and spoint.eid_changes[0][0] == 0 and spoint.eid_changes[entries - 1][1] == hour_ms:
            spoint.eid_changes[0] = [spoint.eid_changes[entries - 1][0], spoint.eid_changes[0][1]]
            spoint.eid_changes.pop()
            entries = entries -1


        if entries == 0 or spoint.eid_changes[0] == [0, hour_ms]:
            print('error 4, {}, {}'.format(entries,spoint.eid_changes))
            spoint.type = SPAWN_UNDEF
            spoint.pauses = -1
            continue
        elif entries == 1:
            spoint.eid_changes = spoint.eid_changes[0]
            changet = (spoint.eid_changes[1] - spoint.eid_changes[0]) % hour_ms
            changet = changet - 2*err_t
        else:
            print('error 5')
            spoint.type = SPAWN_UNDEF
            spoint.pauses = -1
            continue

        #######################################################
        if spoint.pauses == 0: # 1x60 spawn
            if changet <= q_ms + 2*err_t:
                spoint.type = SPAWN_1x60
                spoint.spawntime = spoint.eid_changes[1]
                spoint.pausetime = (spoint.eid_changes[1]-spoint.eid_changes[0]) % hour_ms
            else:
                print('error 6')
                spoint.type = SPAWN_UNDEF
                spoint.pauses = -1
                continue
        elif spoint.pauses == 1:
            spoint.quarter_base = spoint.quarter_base[0]

            qbase15 = spoint.quarter_base
            qbases15 = [qbase15+q_ms, qbase15+2*+q_ms,qbase15+3*q_ms,qbase15+4*q_ms]
            sight_bools = [True,False,False,False]
            for q in range(0,3):
                for qs in spoint.quarter_sights:
                    testq = qs
                    while testq < qbases15[q]:
                        testq += hour_ms
                    if (qbases15[q] < testq < qbases15[q+1]) and (testq-qbases15[q] > (err_t+err_c+1)) and (qbases15[q+1]-testq > (err_t+err_c+1)):
                        sight_bools[q+1] = True


            qbases15 = [qbase15, qbase15 - q_ms, qbase15 - 2 * q_ms, qbase15 - 3 * q_ms]
            dist_bools = [False, False, False, False]
            cmin = spoint.eid_changes[0]
            cmax = spoint.eid_changes[1]
            while cmax < cmin:
                cmax += hour_ms
            for q in range(0, 4):
                while qbases15[q] < cmin:
                    qbases15[q] += hour_ms
                if (cmin < qbases15[q] < cmax and qbases15[q]-cmin > (err_t+err_c+1) and cmax-qbases15[q] > (err_t+err_c+1)):
                    dist_bools[q] = True

            if sight_bools == [True,False,False,False] and 3*q_ms - 2*err_t <= changet < 4*q_ms + 2*err_t:
                spoint.type = SPAWN_1x15
                spoint.pausetime = 45 * 60000
                spoint.spawntime = spoint.quarter_base
            elif sight_bools == [True,False,False,True] and 2*q_ms - 2*err_t <= changet < 3*q_ms + 2*err_t:
                spoint.pausetime = 30 * 60000
                spoint.type = SPAWN_1x30
                spoint.spawntime = (spoint.quarter_base - q_ms) % hour_ms
            elif sight_bools == [True, False, False, True] and changet < q_ms + 2*err_t and dist_bools == [True,False,False,False]:
                spoint.pausetime = 30 * 60000
                spoint.type = SPAWN_1x60h23
                spoint.spawntime = spoint.quarter_base
            elif sight_bools == [True,False,True,True] and q_ms - 2*err_t <= changet < 2*q_ms + 2*err_t:
                spoint.type = SPAWN_1x45
                spoint.pausetime = 15 * 60000
                spoint.spawntime = (spoint.quarter_base - 2*q_ms) % hour_ms
            elif sight_bools == [True,False,True,True] and changet < q_ms + 2*err_t and dist_bools == [False,True,False,False]:
                spoint.type = SPAWN_1x60h3
                spoint.pausetime = 15 * 60000
                spoint.spawntime = (spoint.quarter_base -  q_ms) % hour_ms
            elif sight_bools == [True, False, True, True] and changet < q_ms + 2*err_t and dist_bools == [True,False,False,False]:
                spoint.type = SPAWN_1x60h2
                spoint.pausetime = 15 * 60000
                spoint.spawntime = spoint.quarter_base
            else:
                print('error 7')
                spoint.type = SPAWN_UNDEF
                spoint.pauses = -1
                continue

def main():
    hasinput = False
    for (dirpath, dirnames, filenames) in os.walk('{}/input'.format(workdir)):
        for file in filenames:
            hasinput = True
            readfile(dirpath + '/' + file)
    if hasinput:
        getinfo()
        writefile(workdir+'/output/allspawns.json')
if __name__ == '__main__':
    main()