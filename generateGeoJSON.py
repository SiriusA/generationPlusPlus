from asyncio.windows_events import NULL
from copy import copy
import os
import json, geojson
import statistics
import colorsys
import numpy as np
from PIL import Image
import distutils.core

# making python more pythonic smh
def readfile(filename):
    with open(filename) as file:
        return file.read()

def RectanglesOverlap(p1, p2, p3, p4):
    return p1[0] <= p4[0] and p2[0] >= p3[0] and p1[1] <= p4[1] and p2[1] >= p3[1]

def collinear(p0, p1, p2):
    x1, y1 = p1[0] - p0[0], p1[1] - p0[1]
    x2, y2 = p2[0] - p0[0], p2[1] - p0[1]
    return abs(x1 * y2 - x2 * y1) < 1e-12

## Constants
camfullsize = np.array([1400,800]) # in px
camsize = np.array([1366,768])
camoffset = np.array([17, 18])
ofscreensize = np.array([1200,400])

four_directions = [np.array([-1,0]),np.array([0,-1]),np.array([1,0]),np.array([0,1])]
center_of_tile = np.array([10,10])
# File Paths
screenshots_root = "./py-input"
output_folder = "./Post_Shortcuts_py-output"
streaming_assets = "C:\Program Files (x86)\Steam\steamapps\common\Rain World\RainWorld_Data\StreamingAssets"
mergedmodsprefix = streaming_assets + "\mergedmods\world"
mscprefix = streaming_assets + "\mods\moreslugcats\world"
vanillaprefix = streaming_assets + "\world"

optimize_geometry = True
skip_existing_tiles = False
# None, "yellow, white, red, gourmand, artificer, rivulet, spear, saint, inv", "yellow", "yellow, white, red"
only_slugcat = "white"
# None, "cc", "cc, su, ss, sb, sh"
only_region = "su"
# Export
task_export_tiles = False
task_export_features = True
task_export_room_features = False
task_export_connection_features = False
task_export_geo_features = False
task_export_creatures_features = False
task_export_placedobject_features = False
task_export_shortcut_features = True
task_export_roomtag_features = False
task_export_batmigrationblockages_features = False

# External data
config = {
    "camfullsize":camfullsize,
    "camsize":camsize,
    "camoffset":camoffset,
    "ofscreensize":ofscreensize,
    "four_directions":four_directions,
    "center_of_tile":center_of_tile,
    "screenshots_root":screenshots_root,
    "output_folder":output_folder,
    "streaming_assets":streaming_assets,
    "mergedmodsprefix":mergedmodsprefix,
    "mscprefix":mscprefix,
    "vanillaprefix":vanillaprefix,
    "optimize_geometry":optimize_geometry,
    "skip_existing_tiles":skip_existing_tiles,
    "only_slugcat":only_slugcat,
    "only_region":only_region,
    "task_export_tiles":task_export_tiles,
    "task_export_features":task_export_features,
    "task_export_room_features":task_export_room_features,
    "task_export_connection_features":task_export_connection_features,
    "task_export_geo_features":task_export_geo_features,
    "task_export_creatures_features":task_export_creatures_features,
    "task_export_placedobject_features":task_export_placedobject_features,
    "task_export_roomtag_features":task_export_roomtag_features,
    "task_export_shortcut_features":task_export_shortcut_features,
    "task_export_batmigrationblockages_features":task_export_batmigrationblockages_features
    }

config = readfile("generationPlus.config")

print(config)

def do_slugcat(slugcat: str):
    if only_slugcat is not None and only_slugcat != slugcat:
        return

    print("Found slugcat regions: " + slugcat)
    # cycle through each region for the corresponding slugcats
    for entry in os.scandir(os.path.join(screenshots_root, slugcat)):
        if not entry.is_dir() or len(entry.name) != 2 or (only_region is not None and only_region != entry.name):
            continue
        # record the region acronyms
        print("Found region: " + entry.name)
        with open(os.path.join(entry.path, "metadata.json")) as metadata:
            regiondata = json.load(metadata)
        assert entry.name == str(regiondata['acronym']).lower()
        # get region rooms
        copyingRooms = 'copyRooms' in regiondata
        if copyingRooms:
            with open(os.path.join(screenshots_root, regiondata['copyRooms'], entry.name, "metadata.json")) as metadata:
                copydata = json.load(metadata)
                rooms = copydata['rooms']
                connections = copydata['connections']
        else:
            rooms = regiondata['rooms']
            connections = regiondata['connections']

        if task_export_features or task_export_tiles:
            # pre calc
            for roomname, room in rooms.items():
                room['roomcoords'] = np.array(room['devPos']) * 10 # map coord to room px coords
                if room['cameras'] == None: # ofscreen
                    regiondata['offscreen'] = room
                    room['camcoords'] = None
                    continue
                else:
                    room['camcoords'] = [room['roomcoords'] + (camoffset + np.array(camera)) for camera in room['cameras']]
                    room['tiles'] = [[room['tiles'][x * room['size'][1] + y] for x in range(room['size'][0])] for y in range(room['size'][1])]
            # out main map unit will be room px
            # because only that way we can have the full-res images being loaded with no scaling

            ## Find 'average foreground color'
            if copyingRooms:
                fg_col = tuple((np.array(statistics.mode(tuple(tuple(col) for col in copydata['fgcolors']))) * 255).astype(int).tolist())
                bg_col = tuple((np.array(statistics.mode(tuple(tuple(col) for col in copydata['bgcolors']))) * 255).astype(int).tolist())
                sc_col = tuple((np.array(statistics.mode(tuple(tuple(col) for col in copydata['sccolors']))) * 255).astype(int).tolist())
            else:
                fg_col = tuple((np.array(statistics.mode(tuple(tuple(col) for col in regiondata['fgcolors']))) * 255).astype(int).tolist())
                bg_col = tuple((np.array(statistics.mode(tuple(tuple(col) for col in regiondata['bgcolors']))) * 255).astype(int).tolist())
                sc_col = tuple((np.array(statistics.mode(tuple(tuple(col) for col in regiondata['sccolors']))) * 255).astype(int).tolist())

        if task_export_tiles and not copyingRooms:
            cam_min = np.array([0,0]) 
            cam_max = np.array([0,0])

            ## Find out boundaries of the image
            for roomname, room in rooms.items():
                roomcoords = room['roomcoords']
                if room['cameras'] == None:
                    cam_min = np.min([cam_min, roomcoords], 0)
                    cam_max = np.max([cam_max, roomcoords + ofscreensize],0)
                else:
                    for camcoords in room['camcoords']:
                        cam_min = np.min([cam_min, camcoords + camoffset],0)
                        cam_max = np.max([cam_max, camcoords + camoffset + camsize],0)
    
            ## Building image tiles for each zoom level
            for zoomlevel in range(0, -8, -1):
                print(f"{slugcat}/{entry.name}: z = {zoomlevel}")

                target = os.path.join(output_folder, slugcat, entry.name, str(zoomlevel))
                if not os.path.exists(target):
                    os.makedirs(target, exist_ok=True)

                mulfac = 2**zoomlevel

                # find bounds
                # lower left inclusive, upper right noninclusive
                tile_size = np.array([256,256])
                llb_tile = np.floor(mulfac*cam_min/tile_size).astype(int)
                urb_tile = np.ceil(mulfac*cam_max/tile_size).astype(int)
        
                # Going over the grid, making images
                for tilex in range(llb_tile[0], urb_tile[0]):
                    for tiley in range(llb_tile[1], urb_tile[1]):

                        if skip_existing_tiles and os.path.exists(os.path.join(target, f"{tilex}_{-1 - tiley}.png")):
                            continue

                        # making a tile
                        #print(f"processing {tilex}_{tiley}")
                        current_tile = np.array([tilex,tiley])
                        tilecoords = tile_size * current_tile
                        tileuppercoords = tilecoords + tile_size
                        tile = None #guard

                        currentcamsize = camsize*mulfac

                        # state == imaged. find the overlapping rooms and paste them
                        for roomname, room in rooms.items():
                            # skip rooms with no cameras
                            if room['cameras'] == None:
                                continue
                            for i, camera in enumerate(room['camcoords']):
                                camcoords = camera * mulfac # roomcoords + (camoffset + np.array(camera)) * mulfac # room px to zoom level

                                if RectanglesOverlap(camcoords,camcoords + currentcamsize, tilecoords,tileuppercoords):
                                    if tile == None:
                                        tile = Image.new('RGB', tuple(tile_size.tolist()), fg_col)
                                    #draw
                                    camimg = Image.open(os.path.join(screenshots_root, slugcat, regiondata["acronym"], roomname + f"_{i}.png"))

                                    if mulfac != 1:
                                        # scale cam
                                        camresized = camimg.resize(tuple(np.array([camimg.width*mulfac,camimg.height*mulfac], dtype=int)))
                                        camimg.close()
                                        camimg = camresized

                                    #image has flipped y, tracks off upper left corner
                                    paste_offset = (camcoords.astype(int) + np.array([0, camimg.height], dtype=int)) - (tilecoords + np.array([0, tile_size[1]], dtype=int))
                                    paste_offset[1] = -paste_offset[1]
                                    # bug: despite the docs, paste requires a 4-tuble box, not a simple topleft coordinate
                                    paste_offset = (paste_offset[0], paste_offset[1],paste_offset[0] + camimg.width, paste_offset[1] + camimg.height)
                                    #print(f"paste_offset is {paste_offset}")
                                    tile.paste(camimg, paste_offset)
                                    camimg.close()
                                
                        # done pasting rooms
                        if tile != None:
                            tile.save(os.path.join(target, f"{tilex}_{-1 - tiley}.png"), optimize=True)
                            tile.close()
                            tile = None
            print("done with tiles task")

        if task_export_features:
            features = {}
            target = os.path.join(output_folder, slugcat, entry.name)
            if os.path.exists(os.path.join(target, "region.json")):
                with open(os.path.join(target, "region.json"), 'r') as myin:
                    features = json.load(myin)

            ## Colors
            if copyingRooms:
                features["copyingrooms"] = regiondata['copyRooms']
            features["highlightcolor"] = bg_col
            features["bgcolor"] = fg_col
            features["shortcutcolor"] = sc_col

            bh,bs,bv = colorsys.rgb_to_hsv(bg_col[0]/255.0,bg_col[1]/255.0,bg_col[2]/255.0)
            fh,fs,fv = colorsys.rgb_to_hsv(fg_col[0]/255.0,fg_col[1]/255.0,fg_col[2]/255.0)
            # find good contrasting color
            if abs(bh - fh) < 0.5:
                if bh < fh:
                    bh += 1
                else:
                    fh += 1
            if bs == 0 and fs == 0:
                sh = 0.5
            else:
                #sh = (bh*bs + fh*fs)**2/4/(bs*fs)
                sh = (bh*fs + fh*bs)/(bs+fs)
            while sh > 1:
                sh -= 1
            while sh < 0:
                sh += 1
            ss = ((bs**2 + fs**2)/2.0)**0.5
            sv = ((bv**2 + fv**2)/2.0)**0.5
            if ss < 0.2:
                ss = 0.3 - ss/2.0
            if sv < 0.3:
                sv = 0.45 - sv/2.0
            sr,sg,sb = colorsys.hsv_to_rgb(sh,ss,sv)
            features["geocolor"] = (int(sr*255),int(sg*255),int(sb*255))
        

            ## Rooms
            if task_export_room_features and not copyingRooms:
                room_features = []
                features["room_features"] = room_features
                for roomname, room in rooms.items():
                    roomcoords = room['roomcoords']

                    if room['cameras'] == None:
                        coords = np.array([roomcoords, roomcoords + np.array([0,ofscreensize[1]]), roomcoords + ofscreensize, roomcoords + np.array([ofscreensize[0], 0]), roomcoords]).round(3).tolist()
                        popupcoords = (roomcoords + ofscreensize + np.array([(-ofscreensize[0]/2, 0)])).round().tolist()[0] # single coord
                    else:
                        roomcam_min = room['camcoords'][0]
                        roomcam_max = room['camcoords'][0]
                        for camcoords in room['camcoords']:
                            roomcam_min = np.min([roomcam_min, camcoords],0)
                            roomcam_max = np.max([roomcam_max, camcoords + camsize],0)
                        coords = np.array([roomcam_min, (roomcam_min[0], roomcam_max[1]), roomcam_max, (roomcam_max[0], roomcam_min[1]), roomcam_min]).round(3).tolist()
                        popupcoords = (roomcam_max - np.array([((roomcam_max[0] - roomcam_min[0]), 0)])/2).round().tolist()[0] # single coord
                    #print(f"room {roomname} coords are {coords}")
                    room_features.append(geojson.Feature(
                        geometry=geojson.Polygon([coords,]), # poly expect a list containing a list of coords for each continuous edge
                        properties={
                            "name":roomname,
                            "popupcoords":popupcoords
                        }))

            ## Connections
            if task_export_connection_features and not copyingRooms:
                connection_features = []
                done = []
                features["connection_features"] = connection_features
                for conn in connections:
                    if not conn["roomA"] in rooms or not conn["roomB"] in rooms:
                        print("connection for missing rooms: " + conn["roomA"] + " " + conn["roomB"])
                        continue
                    if (conn["roomA"],conn["roomB"]) in done or (conn["roomB"],conn["roomA"]) in done:
                        print("connection repeated for rooms: " + conn["roomA"] + " " + conn["roomB"])
                        continue

                    coordsA = rooms[conn["roomA"]]["roomcoords"] + np.array(conn["posA"])*20 + center_of_tile
                    coordsB = rooms[conn["roomB"]]["roomcoords"] + np.array(conn["posB"])*20 + center_of_tile
                    dist = np.linalg.norm(coordsA - coordsB)*0.25
                    handleA = coordsA - four_directions[conn["dirA"]] * dist
                    handleB = coordsB - four_directions[conn["dirB"]] * dist
                    connection_features.append(geojson.Feature(
                        geometry=geojson.LineString(np.array([coordsA,handleA,handleB,coordsB]).round().tolist()),
                        properties={

                        }))
                    done.append((conn["roomA"],conn["roomB"]))
                ## Need to add section for conditional links
        
            ## Geometry
            if task_export_geo_features and not copyingRooms:
                geo_features = []
                features["geo_features"] = geo_features
                for roomname, room in rooms.items():
                    print("processing geo for " + roomname)
                    if room['size'] is None:
                        # geo_features.append(geojson.Feature(geojson.MultiLineString([])))
                        continue
                    alllines = []
                    currentrow = []
                    previousrow = []
                    size_x = room['size'][0]
                    size_y = room['size'][1]
                    tiles = room['tiles']
                    roomcoords = room['roomcoords']
                    for y in range(size_y):
                        for x in range(size_x):
                            ## self imposed pragma! (good for optimizing later)
                            # lines must be so that its points are declared in order of increasing X and Y
                            # slopes though just need a consistent behavior all across
                            lines = [] # line buffer
                            # check right, check up
                            if tiles[y][x][0] == 0: # Air tile
                                if (0 <= x+1 < size_x) and (tiles[y][x+1][0] == 1):
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x+0.5, y-0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y+0.5])]))
                                if (0 <= y+1 < size_y) and (tiles[y+1][x][0] == 1):
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y+0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y+0.5])]))
                            if tiles[y][x][0] == 1: # Solid tile
                                if (0 <= x+1 < size_x) and (tiles[y][x+1][0] == 0):
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x+0.5, y-0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y+0.5])]))
                                if (0 <= y+1 < size_y) and (tiles[y+1][x][0] == 0):
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y+0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y+0.5])]))

                            # For slopes you need to find their orientation considering nearby tiles
                            if tiles[y][x][0] == 2: # Slope tile
                                if (0 <= x-1 < size_x)  and tiles[y][x-1][0] == 1:
                                    if (0 <= y-1 < size_y)  and tiles[y-1][x][0] == 1:
                                        lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y+0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y-0.5])]))
                                    elif (0 <= y+1 < size_y)  and tiles[y+1][x][0] == 1:
                                        lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y-0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y+0.5])]))
                                elif (0 <= x+1 < size_x)  and tiles[y][x+1][0] == 1:
                                    if (0 <= y-1 < size_y)  and tiles[y-1][x][0] == 1:
                                        lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y-0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y+0.5])]))
                                    elif (0 <= y+1 < size_y)  and tiles[y+1][x][0] == 1:
                                        lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y+0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y-0.5])]))

                            # Half floors are a pair of lines and possibly more lines to the sides
                            if tiles[y][x][0] == 3: # Half-floor
                                if (0 <= x-1 < size_x) and tiles[y][x-1][0] == 0: # Air to the left
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y]),roomcoords + center_of_tile + 20*np.array([x-0.5, y+0.5])]))
                                elif (0 <= x-1 < size_x) and tiles[y][x-1][0] == 1: # solid to the left
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y-0.5]),roomcoords + center_of_tile + 20*np.array([x-0.5, y])]))
                                if not (tiles[y][x][1] & 1): # gotcha, avoid duplicated line
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y]),roomcoords + center_of_tile + 20*np.array([x+0.5, y])]))
                                lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y+0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y+0.5])]))
                                if (0 <= x+1 < size_x) and tiles[y][x+1][0] == 0: # Air to the right
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x+0.5, y]),roomcoords + center_of_tile + 20*np.array([x+0.5, y+0.5])]))
                                elif (0 <= x+1 < size_x) and tiles[y][x+1][0] == 1: # solid to the right
                                    lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x+0.5, y-0.5]),roomcoords + center_of_tile + 20*np.array([x+0.5, y])]))
                            # Poles
                            if tiles[y][x][1] & 2: # vertical
                                lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x, y-0.5]),roomcoords + center_of_tile + 20*np.array([x, y+0.5])]))

                            if tiles[y][x][1] & 1: # Horizontal
                                lines.append(np.array([roomcoords + center_of_tile + 20*np.array([x-0.5, y]),roomcoords + center_of_tile + 20*np.array([x+0.5, y])]))
                    
                            if not optimize_geometry:
                                currentrow.extend(lines)
                                continue
                            ## reduce considering recent elements
                            for line in lines:
                                cand = None
                                candFrom = None
                                for part in currentrow:
                                    if np.array_equal(part[-1], line[0]):
                                        if collinear(part[-2], line[0], line[1]):
                                            part[-1] = line[1]
                                            line = None
                                            break
                                        elif cand is None:
                                            cand = part
                                            candFrom = currentrow
                                if line is None:
                                    continue
                                for part in previousrow:
                                    if np.array_equal(part[-1], line[0]):
                                        if collinear(part[-2], line[0], line[1]):
                                            part[-1] = line[1]
                                            line = None
                                            previousrow = [p for p in previousrow if p is not part]
                                            currentrow.append(part)
                                            break
                                        elif cand is None:
                                            cand = part
                                            candFrom = previousrow;
                                if line is None:
                                    continue
                                if cand is None:
                                    currentrow.append(line)
                                    continue
                        
                                newcand = np.append(cand, [line[1]],0)
                                if candFrom is currentrow:
                                    currentrow = [p for p in currentrow if p is not cand]
                                else:
                                    previousrow = [p for p in previousrow if p is not cand]
                                currentrow.append(newcand)

                        alllines.extend([p.round().tolist() for p in previousrow])
                        previousrow = currentrow
                        currentrow = []
                    alllines.extend([p.round().tolist() for p in previousrow])
                    if optimize_geometry:
                        ## reduce considering all elements
                        alreadychecked = []
                        for _ in range(len(alllines)): # max iterations
                            touched = False
                            for lineA in alllines:
                                for lineB in alllines:
                                    if lineA is lineB:
                                        continue # my my I didn't recall being this dumb
                                    if np.array_equal(lineA[-1], lineB[0]):
                                        lineA.extend(lineB[1:])
                                        touched = True
                                        alllines.remove(lineB)
                                        break
                                    if np.array_equal(lineA[0], lineB[-1]):
                                        lineB.extend(lineA[1:])
                                        touched = True
                                        alllines.remove(lineA)
                                        break
                                    if np.array_equal(lineA[0], lineB[0]):
                                        lineA.reverse()
                                        lineA.extend(lineB[1:])
                                        touched = True
                                        alllines.remove(lineB)
                                        break
                                    if np.array_equal(lineA[-1], lineB[-1]):
                                        lineA.extend(list(reversed(lineB))[1:])
                                        touched = True
                                        alllines.remove(lineB)
                                        break
                                if touched:
                                    break
                                alllines.remove(lineA)
                                alreadychecked.append(lineA)

                            if not touched:
                                break
                        alllines += alreadychecked
                    #for line in alllines: ## debug individual strokes with different colors
                    #    geo_features.append(geojson.Feature(
                    #    geometry=geojson.LineString(line),
                    #    properties={

                    #    }))
                    geo_features.append(geojson.Feature( # single stroke
                        geometry=geojson.MultiLineString(alllines),
                        properties={
                            "room":roomname
                        }))
        
            ## Creatures
            if task_export_creatures_features:
                creatures_features = []
                features["creatures_features"] = creatures_features
                # grouping together all lizards, and then centipedes pole mimics, for the corresponding attributes mean and number
                MeanWhitelist = ("Pink","PinkLizard","Green","GreenLizard","Blue","BlueLizard","Yellow","YellowLizard","White","WhiteLizard","Black","BlackLizard","Cyan","CyanLizard","Red","RedLizard","Caramel","SpitLizard","Strawberry","ZoopLizard", "Eel","EelLizard","Train","TrainLizard")
                NumberWhitelist = ("PoleMimic","Mimic","SmallCentipede","Centipede","Centi","Cent","Red Centipede","RedCentipede","RedCenti","Red Centi","AquaCenti", "Aqua Centi", "AquaCentipede", "Aqua Centipede", "Aquapede")
                print("creatures task!")
                # read spawns, group spawns into dens (dens have a position)
                dens = {}
                # excludes mean, number, seed, and amount attributes, since those have special handling
                creature_attributes = ("{PreCycle}","{Ignorecycle}","{Night}","{TentacleImmune}","{Lavasafe}","{Voidsea}","{Winter}","{AlternateForm}")
                for spawnentry in regiondata["creatures"]:
                    spawnentry = spawnentry.strip()
                    if not spawnentry:
                        continue

                    if spawnentry.startswith("(X-"):
                        # X- means the creature spawns for every slugcat EXCEPT the listed ones. skip if current slugcat is one of those
                        slugcats_without_creature = [str(s.strip()).lower() for s in spawnentry[3:spawnentry.index(")")].split(",") if s.strip()]
                        if len(slugcats_without_creature) > 0 and slugcat.lower() in slugcats_without_creature:
                            continue
                        spawnentry = spawnentry[spawnentry.index(")")+1:]
                    # creature spawns for listed slugcats. skip if current slugcat isn't one of those
                    elif spawnentry.startswith("("):
                        slugcats_with_creature = [str(s.strip()).lower() for s in spawnentry[1:spawnentry.index(")")].split(",") if s.strip()]
                        if len(slugcats_with_creature) > 0 and slugcat.lower() not in slugcats_with_creature:
                            continue
                        spawnentry = spawnentry[spawnentry.index(")")+1:]

                    arr = spawnentry.split(" : ")
                    ## Lineage-Creatures
                    if arr[0] == "LINEAGE":
                        if len(arr) < 3:
                            print("faulty spawn! missing stuff: " + spawnentry)
                            continue
                        room_name = arr[1]
                        den_index = arr[2]
                        if room_name != "OFFSCREEN" and room_name not in rooms:
                            # creature is in a room that doesn't exist for this region
                            continue
                        if room_name != "OFFSCREEN" and len(rooms[room_name]["nodes"]) <= int(den_index):
                            print("faulty spawn! den index over room nodes: " + spawnentry)
                            continue
                        if room_name != "OFFSCREEN":
                            node = rooms[room_name]["nodes"][int(den_index)]
                            tiles = rooms[room_name]["tiles"]
                            if tiles[node[1]][node[0]][2] != 3:
                                print("faulty spawn! not a den: " + spawnentry)
                                continue

                        spawn = {}
                        spawn["is_lineage"] = True
                        creature_arr = arr[3].split(", ")
                        spawn["lineage"] = [creature.split("-")[0] for creature in creature_arr]
                        # Lineage Creature attributes
                        spawn["lineage_probs"] = [creature.split("-")[-1] for creature in creature_arr]
                        spawn["attributes"] = []
                        print("creature_arr: " + str(creature_arr))
                        for creature in creature_arr:
                            lineageentries = creature.split("-")
                            if len(lineageentries) == 2:
                                spawn["attributes"].append(None)
                                print("No Attributes for " + creature)
                            if len(lineageentries) > 2:
                                print(creature + " Has Attributes")
                                
                                for creature_attr in lineageentries:
                                    # PreCycle, Ignorecycle, Night, TentacleImmune, Lavasafe, Voidsea, Winter, and AlternateForm
                                    for attribute in creature_attributes:
                                        if attribute in arr[3]:
                                            attributekey = attribute.strip("{}").lower()
                                            attribute = {attributekey:True}
                                            spawn["attributes"].append(attribute)
                                    # Mean
                                    if creature_attr.startswith("{Mean:"):
                                        Mean = creature_attr.strip("{Mean:}")
                                        for Lizard in MeanWhitelist:
                                            if lineageentries[0] == Lizard:
                                                spawn["mean"] = Mean
                                                mean = {"mean":Mean}
                                                spawn["attributes"].append(mean)
                                                print("Mean: " + Mean)
                                    # Seed
                                    if creature_attr.startswith("{Seed:"):
                                        Seed = creature_attr.strip("{Seed:}")
                                        seed = {"seed":Seed}
                                        spawn["attributes"].append(seed)
                                        print("Seed: " + Seed)
                                    # Number
                                    if creature_attr.startswith("{") and not creature_attr[0]:
                                        Number = creature_attr.strip("{}")
                                        for Length in NumberWhitelist:
                                            if lineageentries[0] == Length:
                                                number = {"number":Number}
                                                spawn["attributes"].append(number)
                                                print("Number: " + number)

                        print("Creature Attributes: " + str(spawn["attributes"]))

                        denkey = arr[1]+ ":" +arr[2] # room:den
                        if denkey in dens:
                            dens[denkey]["creatures"].append(spawn)
                        else:
                            dens[denkey] = {"room":arr[1],"den":int(arr[2]),"creatures":[spawn]}
                    ## Non-Lineage Creatures
                    else:
                        creature_arr = arr[1].split(", ")
                        room_name = arr[0]
                        for creature_desc in creature_arr:
                            spawn = {}
                            spawn["is_lineage"] = False

                            den_index,spawn["creature"], *attr = creature_desc.split("-")

                            if room_name  != "OFFSCREEN" and room_name not in rooms:
                                # creature is in a room that doesn't exist for this region
                                continue
                            if room_name  != "OFFSCREEN" and len(rooms[room_name]["nodes"]) <= int(den_index):
                                print("faulty spawn! den index over room nodes: " + room_name + " : " + creature_desc)
                                continue
                            if room_name != "OFFSCREEN":
                                node = rooms[room_name]["nodes"][int(den_index)]
                                tiles = rooms[room_name]["tiles"]
                                if tiles[node[1]][node[0]][2] != 3:
                                    print("faulty spawn! not a den: " + spawnentry)
                                    continue

                            # Always implicitly assume a creature amount of 1 when not explicitly defined
                            spawn["amount"] = 1
                            if attr:
                                print("Count: " + str(len(attr)) + ", Attributes: " + str(attr))
                                attrindex = 0
                                while attrindex < len(attr):
                                    # Read creature attributes
                                    if not attr[attrindex].startswith("{"):
                                        try:
                                            spawn["amount"] = int(attr[attrindex])
                                        except:
                                            print("amount not specified. first attribute is \"" + attr[attrindex] + "\" in \"" + room_name + " : " + creature_desc + "\"")
                                            spawn["amount"] = 1
                                    # PreCycle, Ignorecycle, Night, TentacleImmune, Lavasafe, Voidsea, Winter, and AlternateForm
                                    for attribute in creature_attributes:
                                        if attribute in attr:
                                            attributekey = attribute.strip("{}").lower()
                                            spawn[attributekey] = True
                                    # Mean
                                    if attr[attrindex].startswith("{Mean:") in attr:
                                        Mean = attr[attrindex].strip("{Mean:}")
                                        for Lizard in MeanWhitelist:
                                            if spawn["creature"] == Lizard:
                                                if "{Mean:" + Mean + "}" in attr:
                                                    print("Mean: " + Mean)
                                                    spawn["mean"] = Mean
                                    # Seed
                                    if attr[attrindex].startswith("{Seed:") in attr:
                                        Seed = attr[attrindex].strip("{Seed:}")
                                        if "{Seed:" + Seed + "}" in attr:
                                            print("Seed: " + Seed)
                                            spawn["seed"] = Seed
                                    # Number
                                    if attr[attrindex].startswith("{") in attr and not attr[attrindex].find("e") in attr:
                                        number = attr[attrindex].strip("{}")
                                        for Length in NumberWhitelist:
                                            if spawn["creature"] == Length:
                                                if "{" + number + "}" in attr:
                                                    print("Number: " + number)
                                                    spawn["number"] = number

                                    attrindex += 1

                            if spawn["creature"] == "Spider 10": ## Bruh...
                                print("faulty spawn! stupid spiders: " + room_name + " : " + creature_desc)
                                continue ## Game doesnt parse it, so wont I
                            denkey = room_name+ ":" +den_index # room:den
                            if denkey in dens:
                                dens[denkey]["creatures"].append(spawn)
                            else:
                                dens[denkey] = {"room":room_name,"den":int(den_index),"creatures":[spawn]}
                ## process dens into features
                for _,den in dens.items():
                    if den["room"] == "OFFSCREEN":
                        room = regiondata['offscreen']
                        dencoords = room['roomcoords'] + ofscreensize/2
                    else:
                        room = rooms[den["room"]]
                        dencoords = room['roomcoords'] + center_of_tile + 20* np.array(room['nodes'][den["den"]])
                    creatures_features.append(geojson.Feature(
                        geometry=geojson.Point(np.array(dencoords).round().tolist()),
                        properties=den))

                print("creatures task done!")

            ## Placed Objects
            if task_export_placedobject_features:
                placedobject_features = []
                features["placedobject_features"] = placedobject_features
                worldName = regiondata["acronym"].lower()
                mergedmodspath = ""
                vanillapath = ""
                mscpath = ""
                ismergedmods = False
                ismsc = False
                isvanilla = False
                worldsources = ([mscprefix,"MSC",ismsc,mscpath],[mergedmodsprefix,"MergedMods",ismergedmods,mergedmodspath],[vanillaprefix,"Vanilla",isvanilla,vanillapath])
                inroomobjects = [] # the list of collective objects within a singular room
                steampipes = ("SteamPipe","WallSteamer")
                quadobject = ("SpotLight","SuperJumpInstruction","DeepProcessing","CustomDecal")
                gridrectobject = ("ZapCoil","SuperStructureFuses")
                multiplayeritems = ("Rock","Spear","ExplosiveSpear","Bomb","SporePlant")
                collecttokens = ("GoldToken","BlueToken","GreenToken","WhiteToken","RedToken","DevToken")
                consumableobjects = ("SeedCob","DangleFruit","FlareBomb","PuffBall","WaterNut","Jellyfish","KarmaFlower","Mushroom",
                                     "FirecrackerPlant","VultureGrub","DeadVultureGrub","Lantern","SlimeMold","FlyLure","SporePlant",
                                     "BubbleGrass","Hazer","DeadHazer","Germinator","GooieDuck","LillyPuck","GlowWeed",
                                     "MoonCloak","DandelionPeach","HRGuard","VoidSpawnEgg","DataPearl","UniqueDataPearl")
                datapearl = ("DataPearl","UniqueDataPearl")
                resizableobjects = ("CoralCircuit","CoralNeuron","CoralStem","CoralStemWithNeurons","Corruption","CorruptionTube",
                                    "CorruptionDarkness","StuckDaddy","WallMycelia","ProjectedStars","CentipedeAttractor",
                                    "DandelionPatch","NoSpearStickZone","LanternOnStick","TradeOutpost","ScavengerTreasury","ScavTradeInstruction",
                                    "CosmeticSlimeMold","CosmeticSlimeMold2","PlayerPushback","DeadTokenStalk","NoLeviathanStrandingZone","Vine",
                                    "NeuronSpawner","MSArteryPush","BigJellyFish","RotFlyPaper","KarmaShrine","Stowaway","ScavengerOutpost","InsectGroup","Filter")
                print("starting placed object task!")
                # for each room, resolve the exact file path so that it can be referenced and read later
                mscregions = ("rm","vs","ms","lc","hr","cl","oe","ug","dm","lm")
                for roomname, room in rooms.items():
                    roomName = room['roomName'].lower()
                    if roomName.startswith("offscreen"):
                        print(roomname + " is an offscreen room: Skipping!")
                        continue

                    # this whole thing needs optimized, but that is a later task, after the fact for when it works - 7/11/2023: it works now! :)

                    def fileresolver(roomName):
                        # check for gate rooms, not that they have shortcuts... :(
                        if roomName.startswith("gate"):
                            subfolder = "\gates\\"
                            roomtype = "gate"
                        else:
                            subfolder = "\\" + worldName + "-rooms\\"
                            roomtype = "room"

                        # read and write which world sources a room is found in
                        # need to cycle through gate and normal rooms
                        # slugcat specific and general settings, skip this for vanilla and merged

                        pathdata = worldsources
                        for worldsource in pathdata:
                            skipMergedMods = False
                            skipVanilla = False
                            for mscregion in mscregions:
                                if worldName == mscregion and worldsource[1] == "MergedMods":
                                    skipMergedMods = True
                                if worldName == mscregion and worldsource[1] == "Vanilla":
                                    skipVanilla = True

                            if skipMergedMods and roomtype == "room":
                                print("skipping searching in MergedMods since the room is msc exclusive")
                                continue
                            if skipVanilla and roomtype == "room":
                                print("skipping searching in Vanilla since the room is msc exclusive")
                                continue
                            foundspecific = False
                            specificsetting = ""
                            specifictext = ""
                            # when world source is msc, check for slugcat specific settings, and if they exist, use them instead
                            if worldsource == pathdata[0]:
                                specificsetting = "-" + slugcat
                                specifictext = " for " + slugcat

                                settingspath = worldsource[0] + subfolder + roomname + "_settings" + specificsetting + ".txt"
                                if (os.path.exists(settingspath)):
                                    print("Found " + roomname + " settings" + specifictext + " in " + worldsource[1])
                                    worldsource[2] = True
                                    worldsource[3] = settingspath
                                    foundspecific = True
                                else:
                                    worldsource[2] = False
                                    worldsource[3] = ""
                                    print("No specific settings in " + worldsource[1])
                            # Onto normal settings
                            specificsetting = ""
                            specifictext = ""
                            settingspath = worldsource[0] + subfolder + roomname + "_settings" + specificsetting + ".txt"
                            if (os.path.exists(settingspath)):
                                print("Found " + roomname + " settings" + specifictext + " in " + worldsource[1])
                                worldsource[2] = True
                                worldsource[3] = settingspath
                            else:
                                # only overwrite if specific doesn't exist
                                if not foundspecific:
                                    worldsource[2] = False
                                    worldsource[3] = ""
                                print("No generic settings in " + worldsource[1])
                            
                        # MSC FIRST
                        # NOT mergedmods first; will cause issues with duplicate gates in msc and vanilla, since their actual per region usage isn't explicit
                        # about modifed and merged files; if a file exists in msc, it will only be a full file, either original or overwriting, whereas modified files
                        # will be found in mergedmods as complete files, if not found in msc
                        if not pathdata[0][2]:
                            # MERGEDMODS SECOND
                            # NOT msc second; will cause issues with duplicate gates in msc and vanilla, since their actual per region usage isn't explicit
                            if not pathdata[1][2]:
                                # vanilla is last priority
                                if not pathdata[2][2]:
                                    print(roomname + " is not in any world file")
                                else:
                                    resolvedpath = pathdata[2][3]
                                    print("this is vanilla")
                            else:
                                resolvedpath = pathdata[1][3]
                                print("this is mergedmods")
                        else:
                            resolvedpath = pathdata[0][3]
                            print("this is msc")

                        # make sure that the resolved path and world source are the same
                        if resolvedpath:
                            print("Using " + resolvedpath)
                            return resolvedpath

                    path = fileresolver(roomName)

                    # convert each settings file into a list of placed objects
                    with open(path, 'r', encoding="utf-8") as f:
                        readall = f.readlines()
                        hasplacedobjects = False
                        insideofplacedobjects = False
                        for readline in readall:
                            if (readline.startswith("PlacedObjects: ")):
                                insideofplacedobjects = True;
                                hasplacedobjects = True
                                rawplacedobjects = readline
                            elif (not readline.startswith("PlacedObjects: ")):
                                insideofplacedobjects = False;
                            elif (insideofplacedobjects):
                                rawplacedobjects = readline
                        if not hasplacedobjects:
                            print("No Placed Objects in " + roomname + ", Skipping!")
                            f.close()
                            continue
                       
                    f.close()

                    rawplacedobjects = str(rawplacedobjects).partition(": ")[-1].rstrip(", \n")
                    listplacedobjects = rawplacedobjects.split(", ")

                    # since objects have independent positions, each object has its own geometry, properties pair
                    for roomobject in listplacedobjects:
                        if len(roomobject) <= 3:
                            print("object is a stub, skipping")
                            continue
                        elif "><" not in roomobject:
                            print("Object " + roomobject + ' does not contain "><" value delimiters, ')
                            roomobject.split("~")

                            PlacedObject = {
                                "object":"Unknown",
                                "data":roomobject
                                }

                            placedobject_features.append(geojson.Feature(
                                properties=PlacedObject))
                        else:
                            objectentry = roomobject.split("><")
                            objectname = objectentry[0]
                            objectposx = objectentry[1]
                            objectposy = objectentry[2]
                            objectdata = objectentry[3].split("~")

                            data = objectdata
                            # Hefty-ass load of unique instances of object data
                            for placedobject in steampipes:
                                if objectname == placedobject:
                                    data = {
                                        "handlePosX":objectdata[0],
                                        "handlePosY":objectdata[1]
                                        }

                            for placedobject in quadobject:
                                if objectname == placedobject:
                                    data = {
                                        "handles[0]X":objectdata[0],
                                        "handles[0]Y":objectdata[1],
                                        "handles[1]X":objectdata[2],
                                        "handles[1]Y":objectdata[3],
                                        "handles[2]X":objectdata[4],
                                        "handles[2]Y":objectdata[5]
                                        }

                                if objectname == "CustomDecal":
                                    data = {
                                        "handles[0]X":objectdata[0],
                                        "handles[0]Y":objectdata[1],
                                        "handles[1]X":objectdata[2],
                                        "handles[1]Y":objectdata[3],
                                        "handles[2]X":objectdata[4],
                                        "handles[2]Y":objectdata[5],
                                        "panelPosX":objectdata[6],
                                        "panelPosY":objectdata[7],
                                        "fromDepth":objectdata[8],
                                        "toDepth":objectdata[9],
                                        "noise":objectdata[10],
                                        "imageName":objectdata[11]
                                        }
                                    if len(objectdata) >= 20:
                                        vertices = []
                                        l = 12
                                        while l < len(objectdata):
                                            vertices.append(objectdata[l])
                                            l += 1

                                        data = {
                                            "handles[0]X":objectdata[0],
                                            "handles[0]Y":objectdata[1],
                                            "handles[1]X":objectdata[2],
                                            "handles[1]Y":objectdata[3],
                                            "handles[2]X":objectdata[4],
                                            "handles[2]Y":objectdata[5],
                                            "panelPosX":objectdata[6],
                                            "panelPosY":objectdata[7],
                                            "fromDepth":objectdata[8],
                                            "toDepth":objectdata[9],
                                            "noise":objectdata[10],
                                            "imageName":objectdata[11],
                                            "vertices":vertices
                                            }

                                if objectname == "DeepProcessing":
                                    data = {
                                        "handles[0]X":objectdata[0],
                                        "handles[0]Y":objectdata[1],
                                        "handles[1]X":objectdata[2],
                                        "handles[1]Y":objectdata[3],
                                        "handles[2]X":objectdata[4],
                                        "handles[2]Y":objectdata[5],
                                        "panelPosX":objectdata[6],
                                        "panelPosY":objectdata[7],
                                        "fromDepth":objectdata[8],
                                        "toDepth":objectdata[9],
                                        "intensity":objectdata[10]
                                        }

                            for placedobject in gridrectobject:
                                if objectname == placedobject:
                                    data = {
                                        "handlePosX":objectdata[0],
                                        "handlePosY":objectdata[1]
                                        }

                            for placedobject in multiplayeritems:
                                if objectname == placedobject:
                                    data = {
                                        "type":objectdata[0],
                                        "panelPosX":objectdata[1],
                                        "panelPosY":objectdata[2],
                                        "chance":objectdata[3]
                                        }

                            for placedobject in collecttokens:
                                if objectname == placedobject:
                                    if path.startswith(vanillaprefix):
                                        data = {
                                            "handlePosX":objectdata[0],
                                            "handlePosY":objectdata[1],
                                            "panelPosX":objectdata[2],
                                            "panelPos":objectdata[3],
                                            "isBlue":objectdata[4],
                                            "tokenString":objectdata[5],
                                            "availableToPlayers":objectdata[6]
                                        }
                                    else:
                                        if len(objectdata) == 11:
                                            data = {
                                            "handlePosX":objectdata[0],
                                            "handlePosY":objectdata[1],
                                            "panelPosX":objectdata[2],
                                            "panelPos":objectdata[3],
                                            "isBlue":objectdata[4],
                                            "tokenString":objectdata[5],
                                            "availableToPlayers":objectdata[6],
                                            "isGreen":objectdata[7],
                                            "isWhite":objectdata[8],
                                            "isRed":objectdata[9],
                                            "isDev":objectdata[10]
                                            }           

                            for placedobject in consumableobjects:
                                if objectname == placedobject:
                                    if len(objectdata) > 3:
                                        data = {
                                            "panelPosX":objectdata[0],
                                            "panelPosY":objectdata[1],
                                            "minRegen":objectdata[2],
                                            "maxRegen":objectdata[3]
                                            }

                                if objectname == "VoidSpawnEgg":
                                    if len(objectdata) >= 5:
                                        data = {
                                            "panelPosX":objectdata[0],
                                            "panelPosY":objectdata[1],
                                            "minRegen":objectdata[2],
                                            "maxRegen":objectdata[3],
                                            "exit":objectdata[4]
                                            }

                                for placedobject in datapearl:
                                    if objectname == placedobject:
                                        if len(objectdata) >= 5:
                                            data = {
                                                "panelPosX":objectdata[0],
                                                "panelPosY":objectdata[1],
                                                "minRegen":objectdata[2],
                                                "maxRegen":objectdata[3],
                                                "pearlType":objectdata[4],
                                                "hidden":objectdata[5]
                                                }

                            for placedobject in resizableobjects:
                                if objectname == placedobject:
                                    data = {
                                    "handlePosX":objectdata[0],
                                    "handlePosY":objectdata[1]
                                    }

                                if objectname == "Filter":
                                    data = {
                                        "handlePosX":objectdata[0],
                                        "handlePosY":objectdata[1],
                                        "panelPosX":objectdata[2],
                                        "panelPosY":objectdata[3],
                                        "availableToPlayers":objectdata[4]
                                        }

                                elif objectname == "InsectGroup":
                                    data = {
                                        "handlePosX":objectdata[0],
                                        "handlePosY":objectdata[1],
                                        "panelPosX":objectdata[2],
                                        "panelPosY":objectdata[3],
                                        "insectType":objectdata[4],
                                        "density":objectdata[5]
                                        }

                                elif objectname == "ScavengerOutpost":
                                    data = {
                                        "handlePosX":objectdata[0],
                                        "handlePosY":objectdata[1],
                                        "panelPosX":objectdata[2],
                                        "panelPosY":objectdata[3],
                                        "direction":objectdata[4],
                                        "skullSeed":objectdata[5],
                                        "pearlsSeed":objectdata[6]
                                        }

                            if objectname == "LightSource":
                                data = {
                                    "strength":objectdata[0],
                                    "colorType":objectdata[1],
                                    "handlePosX":objectdata[2],
                                    "handlePosY":objectdata[3],
                                    "panelPosX":objectdata[4],
                                    "panelPosY":objectdata[5],
                                    "fadeWithSun":bool(objectdata[6]),
                                    "flat":bool(objectdata[7]),
                                    }
                                if len(objectdata) > 10:
                                    data = {
                                    "strength":objectdata[0],
                                    "colorType":objectdata[1],
                                    "handlePosX":objectdata[2],
                                    "handlePosY":objectdata[3],
                                    "panelPosX":objectdata[4],
                                    "panelPosY":objectdata[5],
                                    "fadeWithSun":bool(objectdata[6]),
                                    "flat":bool(objectdata[7]),
                                    "blinkType":objectdata[8],
                                    "blinkRate":objectdata[9],
                                    "nightLight":bool(objectdata[10])
                                    }
                                elif len(objectdata) > 8:
                                    data = {
                                    "strength":objectdata[0],
                                    "colorType":objectdata[1],
                                    "handlePosX":objectdata[2],
                                    "handlePosY":objectdata[3],
                                    "panelPosX":objectdata[4],
                                    "panelPosY":objectdata[5],
                                    "fadeWithSun":bool(objectdata[6]),
                                    "flat":bool(objectdata[7]),
                                    "blinkType":objectdata[8],
                                    "blinkRate":objectdata[9],
                                    }
                                    
                            elif objectname == "LightFixture":
                                data = {
                                    "type":objectdata[0],
                                    "panelPosX":objectdata[1],
                                    "panelPosY":objectdata[2],
                                    "randomSeed":objectdata[3]
                                    }

                            elif objectname == "SSLightRod":
                                data = {
                                    "panelPosX":objectdata[0],
                                    "panelPosY":objectdata[1],
                                    "depth":objectdata[2],
                                    "rotation":objectdata[3],
                                    "length":objectdata[4],
                                    "brightness":objectdata[5]
                                    }

                            elif objectname == "CellDistortion":
                                data = {
                                    "handlePosX":objectdata[0],
                                    "handlePosY":objectdata[1],
                                    "panelPosX":objectdata[2],
                                    "panelPosY":objectdata[3],
                                    "intensity":objectdata[4],
                                    "scale":objectdata[5],
                                    "chromaticIntensity":objectdata[6],
                                    "timeMult":objectdata[7]
                                    }

                            elif objectname == "OESphere":
                                data = {
                                    "handlePosX":objectdata[0],
                                    "handlePosY":objectdata[1],
                                    "panelPosX":objectdata[2],
                                    "panelPosY":objectdata[3],
                                    "depth":objectdata[4],
                                    "intensity":objectdata[5]
                                    }

                            elif objectname == "SnowSource":
                                data = {
                                    "shape":objectdata[0],
                                    "handlePosX":objectdata[1],
                                    "handlePosY":objectdata[2],
                                    "panelPosX":objectdata[3],
                                    "panelPosY":objectdata[4],
                                    "intensity":objectdata[5],
                                    "noisiness":objectdata[6]
                                    }

                            elif objectname == "LocalBlizzard":
                                data = {
                                    "handlePosX":objectdata[0],
                                    "handlePosY":objectdata[1],
                                    "panelPosX":objectdata[2],
                                    "panelPosY":objectdata[3],
                                    "intensity":objectdata[4],
                                    "scale":objectdata[5],
                                    "angle":objectdata[6]
                                    }

                            elif objectname == "LightingMachine":
                                data = {
                                    "panelPosX":objectdata[0],
                                    "panelPosY":objectdata[1],
                                    "posX":objectdata[2],
                                    "posY":objectdata[3],
                                    "startPointX":objectdata[4],
                                    "startPointY":objectdata[5],
                                    "endPointX":objectdata[5],
                                    "endPointY":objectdata[6],
                                    "chance":objectdata[7],
                                    "permanent":objectdata[8],
                                    "radial":objectdata[9],
                                    "width":objectdata[10],
                                    "intensity":objectdata[11],
                                    "lifeTime":objectdata[12],
                                    "lightingParam":objectdata[13],
                                    "lightingType":objectdata[14],
                                    "impact":objectdata[15],
                                    "volume":objectdata[16],
                                    "soundType":objectdata[17],
                                    "random":bool(objectdata[18]),
                                    "light":bool(objectdata[19])
                                    }

                            elif objectname == "EnergySwirl":
                                data = {
                                    "colorType":objectdata[0],
                                    "handlePosX":objectdata[1],
                                    "handlePosY":objectdata[2],
                                    "panelPosX":objectdata[3],
                                    "panelPosY":objectdata[4],
                                    "depth":objectdata[5]
                                    }

                            elif objectname == "DayNightSettings":
                                data = {
                                    "panelPosX":objectdata[0],
                                    "panelPosY":objectdata[1],
                                    "duskPalette":objectdata[2],
                                    "nightPalette":objectdata[3]
                                    }

                            elif objectname == "FairyParticleSettings":
                                data = {
                                    "panelPosX":objectdata[0],
                                    "panelPosY":objectdata[1],
                                    "absPulse":bool(objectdata[2]),
                                    "pulseMin":objectdata[3],
                                    "pulseMax":objectdata[4],
                                    "pulseRate":objectdata[5],
                                    "scaleMin":objectdata[6],
                                    "scaleMax":objectdata[7],
                                    "interpDurMin":objectdata[8],
                                    "interpDurMax":objectdata[9],
                                    "interpDistMin":objectdata[10],
                                    "interpDistMax":objectdata[11],
                                    "dirDevMin":objectdata[12],
                                    "dirDevMax":objectdata[13],
                                    "dirMin":objectdata[14],
                                    "dirMax":objectdata[15],
                                    "colorHmin":objectdata[16],
                                    "colorHmax":objectdata[17],
                                    "colorSmin":objectdata[18],
                                    "colorSmax":objectdata[19],
                                    "colorLmin":objectdata[20],
                                    "colorLmax":objectdata[21],
                                    "interpTrans":objectdata[22],
                                    "alphaTrans":objectdata[23],
                                    "numKeyframes":objectdata[24],
                                    "spriteType":objectdata[25],
                                    "dirLerpType":objectdata[26],
                                    "speedLerpType":objectdata[27],
                                    "glowRad":objectdata[28],
                                    "glowStrength":objectdata[29],
                                    "rotationRate":objectdata[30]
                                    }

                            PlacedObject = {
                                "room":roomname,
                                "object":objectname,
                                "data":data
                                }

                            objectcoords = room['roomcoords'] + center_of_tile + np.array([float(objectposx),float(objectposy)])
                            placedobject_features.append(geojson.Feature(
                                geometry=geojson.Point(np.array(objectcoords).round().tolist()),
                                properties=PlacedObject))

                # were it so easy
                print("placed object task done!")
           
            ##Shortcuts
            if task_export_shortcut_features:
                shortcut_features = []
                features["shortcut_features"] = shortcut_features
                worldName = regiondata["acronym"].lower()
                mergedmodspath = ""
                vanillapath = ""
                mscpath = ""
                ismergedmods = False
                ismsc = False
                isvanilla = False
                dodimensions = True
                dolight = False
                docamera = False
                doborder = False
                donodes = True
                doshortcuts = False
                mscregions = ("rm","vs","ms","lc","hr","cl","oe","ug","dm","lm")
                worldsources = ([mscprefix,"MSC",ismsc,mscpath],[mergedmodsprefix,"MergedMods",ismergedmods,mergedmodspath],[vanillaprefix,"Vanilla",isvanilla,vanillapath])
                print("starting shortcut task!")
                for roomname, room in rooms.items():
                    roomName = room['roomName'].lower()
                    room['roomcoords'] = np.array(room['devPos']) * 10 # map coord to room px coords

                    if roomName.startswith("offscreen"): # or roomName.startswith("gate")
                        print("Offscreen rooms do not have shortcuts: Skipping " + roomname + "!")
                        continue

                    # redundant and blatant plagarism of my placed objects code, oh well...
                    # No need to capture the isolated gate shelters within the vanilla world file, its not like they contain shortcuts '\_:\_/'

                    def fileresolver(roomName):
                        # GATE SHELTERS SMH
                        # check for gate rooms, not that they have shortcuts... :(
                        # read and write which world sources a room is found in
                        # need to cycle through gate and normal rooms
                        # slugcat specific and general settings, skip this for vanilla and merged

                        pathdata = worldsources
                        for worldsource in pathdata:
                            if roomName.startswith("gate"):
                                subfolder = "\gates\\"
                                roomtype = "gate"
                            else:
                                subfolder = "\\" + worldName + "-rooms\\"
                                roomtype = "room"

                            skipMergedMods = False
                            skipVanilla = False
                            for mscregion in mscregions:
                                if worldName == mscregion and worldsource[1] == "MergedMods":
                                    skipMergedMods = True
                                if worldName == mscregion and worldsource[1] == "Vanilla":
                                    skipVanilla = True

                            if skipMergedMods and roomtype == "room":
                                print("skipping MergedMods: msc exclusive room")
                                continue
                            if skipVanilla and roomtype == "room":
                                print("skipping Vanilla: msc exclusive room")
                                continue
                            
                            roomfilepath = worldsource[0] + subfolder + roomname + ".txt"
                            if (os.path.exists(roomfilepath)):
                                print("Found " + roomtype + " " + roomname + " file in " + worldsource[1])
                                worldsource[2] = True
                                worldsource[3] = roomfilepath
                            else:
                                if worldsource[1] == "Vanilla":
                                    print("No " + roomtype + " file in " + worldsource[1] + " : Checking the gate shelters folder")
                                    subfolder = "\gate shelters\\"
                                    roomtype = "gate shelter"
                                    roomfilepath = worldsource[0] + subfolder + roomname + ".txt"
                                    if (os.path.exists(roomfilepath)):
                                        print("Found " + roomtype + " " + roomname + " file in " + worldsource[1])
                                        worldsource[2] = True
                                        worldsource[3] = roomfilepath
                                else:
                                    print("No " + roomtype + " file in " + worldsource[1])
                                    continue
                            
                        # MSC FIRST
                        # NOT mergedmods first; will cause issues with duplicate gates in msc and vanilla, since their actual per region usage isn't explicit
                        # about modifed and merged files; if a file exists in msc, it will only be a full file, either original or overwriting, whereas modified files
                        # will be found in mergedmods as complete files, if not found in msc
                        
                        mscusedname = os.path.basename(pathdata[0][3]).replace(".txt","")
                        mergedmodsusedname = os.path.basename(pathdata[1][3]).replace(".txt","")
                        vanillausedname = os.path.basename(pathdata[2][3]).replace(".txt","")

                        resolvedpath = ""
                        if not pathdata[0][2] and mscusedname != roomname:
                            # MERGEDMODS SECOND
                            # NOT msc second; will cause issues with duplicate gates in msc and vanilla, since their actual per region usage isn't explicit
                            if not pathdata[1][2] and mergedmodsusedname != roomname:
                                # vanilla is last priority
                                if not pathdata[2][2] and vanillausedname != roomname:
                                    print(roomname + " is not in any world file")
                                elif vanillausedname == roomname:
                                    resolvedpath = pathdata[2][3]
                                    print("this is vanilla")
                            elif mergedmodsusedname == roomname:
                                resolvedpath = pathdata[1][3]
                                print("this is mergedmods")
                        elif mscusedname == roomname:
                            resolvedpath = pathdata[0][3]
                            print("this is msc")
                        else:
                            if mscusedname == roomname:
                                resolvedpath = pathdata[0][3]
                                print("matched msc")
                            if mergedmodsusedname == roomname:
                                resolvedpath = pathdata[1][3]
                                print("matched mergedmods")
                            if vanillausedname == roomname:
                                resolvedpath = pathdata[2][3]
                                print("matched vanilla")

                        # make sure that the resolved path and world source are the same
                        if resolvedpath != "":
                            print("Using " + resolvedpath)
                            return resolvedpath

                    filepath = fileresolver(roomName)

                    # Get the connection map at line 10, and room tiles at line 12
                    with open(filepath, 'r', encoding="utf-8") as f:
                        roomfile = f.readlines()
                        roomnameline = 1
                        dimensionline = 2
                        lightline = 3
                        cameraline = 4
                        borderline = 5
                        itemline = 6
                        if len(roomfile) == 12:
                            shortcutline = 10
                            roomtilesline = 12
                        elif len(roomfile) == 8:
                            shortcutline = 6
                            roomtilesline = 8

                        print("length of roomfile: " + str(len(roomfile)))

                        i = 1
                        while i < len(roomfile):
                            for line in roomfile:
                                if i == roomnameline:
                                    print("found room name at line " + str(i) + " in " + os.path.basename(filepath))
                                    fileroomname = line
                                if i == dimensionline and dodimensions:
                                    print("found dimensions at line " + str(i) + " in " + os.path.basename(filepath))
                                    roomdimensions = line
                                if i == lightline and dolight:
                                    print("found light data at line " + str(i) + " in " + os.path.basename(filepath))
                                    roomlight = line
                                if i == cameraline and docamera:
                                    print("found camera map at line " + str(i) + " in " + os.path.basename(filepath))
                                    roomcameras = line
                                if i == borderline and doborder:
                                    print("found border type at line " + str(i) + " in " + os.path.basename(filepath))
                                    roomborder = line
                                if i == itemline:
                                    print("found items at line " + str(i) + " in " + os.path.basename(filepath))
                                    roomitems = line
                                if i == shortcutline and doshortcuts:
                                    print("found connection map at line " + str(i) + " in " + os.path.basename(filepath))
                                    connectionsmap = line
                                if i == roomtilesline and donodes:
                                    print("found room tiles at line " + str(i) + " in " + os.path.basename(filepath))
                                    roomfilenodes = line

                                i += 1

                    if dodimensions:
                        roomdimensions = roomdimensions.strip("\n").split("|")
                        roomdim = roomdimensions[0].split("*")
                        roomwidth = int(roomdim[0])
                        roomheight = int(roomdim[1])
                        waterlevel = roomdimensions[1]
                        infrontofterrain = roomdimensions[2]

                    if dolight:
                        roomlight = roomlight.strip("\n").split("|")
                        roomangle = roomlight[0].split("*")
                        angle1 = roomangle[0]
                        angle2 = roomangle[1]
                        value3 = roomlight[1]
                        value4 = roomlight[2]

                    if docamera:
                        cameras = {}
                        roomcameras = roomcameras.strip("\n").split("|")
                        cameraindex = 0
                        cameralist = []
                        for camera in roomcameras:
                            camera = roomcameras[camera.index(camera)]
                            coords = camera.split(",")
                            camX = coords[0]
                            camY = coords[1]
                        
                            cameras = ("camera: " + camera,"camX: " + camX,"camY: " + camY)

                            cameralist.append(cameras)
                            cameraindex += 1

                    if doborder:
                        roomborder = roomborder.strip("Border: \n")
                        itemslist = []
                        if len(roomitems) > 1:
                            items = {}
                            roomitems = roomitems.rstrip("|\n").split("|")
                            for item in roomitems:
                                item = item.split(",")
                                iitem = item[0]
                                tileX = item[1]
                                tileY = item[2]
                                items = ("item: " + str(iitem),"tileX" + str(tileX),"tileY" + str(tileY))

                                itemslist.append(items)

                    roomcoords = room['roomcoords']
                    size_x = room['size'][0]
                    size_y = room['size'][1]
                    if donodes:
                        # Find Nodes and Other good stuff
                        roomfilenodes = roomfilenodes.rstrip("|\n").split("|")
                        terraintypes = ("Air","Solid","Slope","Floor","ShortcutEntrance")
                        shortcuttypes = ("DeadEnd","Normal","RoomExit","CreatureHole","NPCTransportation","RegionTransportation")
                        roomnodetypes = ("Exit","Den","RegionTransportation","SideExit","SkyExit","SeaExit","BatHive","GarbageHoles")
                        # simple in room coords
                        roomtilecoords = []
                        roomtiledata = []
                        roomtiles = []
                        tilecolumn = []
                        tilearray = []

                        # convert file nodes into an array, not just a list
                        print("room width: " + str(size_x))
                        print("room height: " + str(size_y))
                        print("length of roomfilenodes: " + str(len(roomfilenodes)))
                        print("width times height: " + str((size_x * size_y)))
                        for column in range(0,size_x):
                            tilecolumn = []
                            for tile in range((size_y * column) - size_y,size_y * column):
                                tilecolumn.append(roomfilenodes[tile])

                            tilearray.append((tilecolumn))
                            #print("Length of column " + str(column) + ": " + str(len(tilecolumn)))
                            #print(tilecolumn)

                        # top down, left right
                        # Start at vertical columns
                        for x in range(1,size_x,1):
                            tileX = x
                            # cycle through the same x, changing in y, the horizontal rows
                            # Start at top left, tile 0,0, then go down, increasing in y until reaching size_y, then stepping to the right by 1 x, starting from the top down again
                            # start with highest Y, uhm well we need to invert the current y coords, since the first tile is actually at the max y in terms of having an origin at the bottom left
                            for y in range(1,size_y,1):
                                tileIsWorthy = False
                                tileY = y
                                tilecoords = (tileX - 1,(size_y - tileY - 1))

                                tile = tilearray[tileX][tileY]
                                # start at 0, end at x*y
                                tileentries = tile.split(",")
                                terraintype = int(tileentries[0])

                                if terraintype == 0:
                                    terraintype = terraintypes[0]
                                if terraintype == 1:
                                    terraintype = terraintypes[1]
                                if terraintype == 2:
                                    terraintype = terraintypes[2]
                                if terraintype == 3:
                                    terraintype = terraintypes[3]
                                if terraintype == 4:
                                    terraintype = terraintypes[4]
                                    tileIsWorthy = True
                                tileattributes = []
                                v = 1
                                while v < len(tileentries):
                                    tileattributes.append(tileentries[v])
                                    v += 1

                                verticalbeam = False
                                horizontalbeam = False
                                shortcut = None
                                wallbehind = False
                                hivetile = False
                                waterfall = False
                                garbagehole = False
                                wormgrass = False

                                tiledata = {}
                                tiledata["coordX"] = tilecoords[0]
                                tiledata["coordY"] = tilecoords[1]
                                tiledata["terrain"] = terraintype
                                
                                for value in tileattributes:
                                    value = int(value)
                                    if value == 1:
                                        tiledata["verticalbeam"] = True
                                    if value == 2:
                                        tiledata["horizontalbeam"] = True
                                    if value == 3:
                                        tiledata["shortcut"] = shortcuttypes[1]
                                        tileIsWorthy = True
                                    if value == 4:
                                        tiledata["shortcut"] = shortcuttypes[2]
                                        tileIsWorthy = True
                                    if value == 5:
                                        tiledata["shortcut"] = shortcuttypes[3]
                                        tileIsWorthy = True
                                    if value == 6:
                                        tiledata["wallbehind"] = True
                                    if value == 7:
                                        tiledata["hivetile"] = True
                                        tileIsWorthy = True
                                    if value == 8:
                                        tiledata["waterfall"] = True
                                        tileIsWorthy = True
                                    if value == 9:
                                        tiledata["shortcut"] = shortcuttypes[4]
                                        tileIsWorthy = True
                                    if value == 10:
                                        tiledata["garbagehole"] = True
                                        tileIsWorthy = True
                                    if value == 11:
                                        tiledata["wormgrass"] = True
                                        tileIsWorthy = True
                                    if value == 12:
                                        tiledata["shortcut"] = shortcuttypes[5]
                                        tileIsWorthy = True

                                # only record significant tiles
                                if tileIsWorthy:
                                    roomtiledata.append(tilecoords)
                                    #roomtiles.append(tiledata)
                                    nodecoords = room['roomcoords'] + center_of_tile + 20* np.array(tilecoords)
                                    shortcut_features.append(geojson.Feature(
                                        geometry=geojson.Point(np.array(nodecoords).round().tolist()),
                                        properties={
                                            "roomname":roomname,
                                            "roomtile":tiledata,
                                            }))

                                #roomtilecoords.append(tilecoords)

                        # Take the proccessed worthy tile array, then match up adjacent tiles of the same type
                      #  for worthytile in tilearray:
                          #  if worthytile.terrain == "Solid" and worthytile.shorcut == "Normal


                    #print(roomtilecoords)
                    print(roomtiledata)

                    if doshortcuts:
                        roomshortcuts = []
                        a = str(connectionsmap).rstrip("|\n")
                        b = a.split("|")
                        shortcutsheader = {
                            "roomgen":b[0],
                            "roomlength":b[1],
                            "roommaplength":b[2]
                            }

                        l = 3
                        connpaths = []
                        while l < len(b):
                            connpaths.append(b[l])
                            l += 1

                        shortcuts = []
                        for connpath in connpaths:
                            c = str(connpath).rstrip(",").split(",")
                            connheader = {
                                "type":c[0],
                                "shortcutlength":c[1],
                                "submerged":c[2],
                                "viewedbycamera":c[3],
                                "entrancewidth":c[4]
                                }

                            e = 5
                            connectivity = []
                            while e < len(c):
                                connectivity.append(c[e])
                                e += 1

                            connpairs = []
                            shortcut = []
                            for connpair in connectivity:
                                d = str(connpair).split(" ")
                                connpairs.append((d[0],d[1]))

                            shortcut = (connheader,connpairs)

                            shortcuts.append(shortcut) 

                        roomheader = {
                            "room":roomname
                            }
                        roomshortcuts = (roomheader,shortcutsheader,shortcuts)
                        shortcut_features.append(geojson.Feature(
                            geometry=geojson.MultiLineString(),
                            properties=roomshortcuts))
                print("shortcuts task done!")

            ## RoomTags
            if task_export_roomtag_features:
                roomtag_features = []
                features["roomtag_features"] = roomtag_features
                roomtags = ("GATE","SWARMROOM","SHELTER","ANCIENTSHELTER","SCAVOUTPOST","SCAVTRADER","PERF_HEAVY","NOTRACKERS","ARENA")
                print("room tag task!")
                for roomentry in regiondata["roomtags"]:
                    roomentry = roomentry.strip()
                    tagroomname = roomentry.partition(" : ")[0]
                    roomtag = roomentry.partition(" : ")[2].partition(" : ")[2]

                    for roomname, room in rooms.items():
                        if tagroomname == roomname:
                            roomcam_min = room['camcoords'][0]
                            roomcam_max = room['camcoords'][0]
                            for camcoords in room['camcoords']:
                                roomcam_min = np.min([roomcam_min, camcoords],0)
                                roomcam_max = np.max([roomcam_max, camcoords + camsize],0)
                            popupcoords = (roomcam_max - np.array([((roomcam_max[0] - roomcam_min[0]), 0)])/2).round().tolist()[0]
                            for tagentry in roomtags:
                                if roomtag == tagentry:
                                    print("tagged " + tagroomname + " as " + tagentry)
                                    roomtag_features.append(geojson.Feature(
                                        geometry = geojson.Point(np.array(popupcoords).round().tolist()),
                                        properties = {
                                            "room":tagroomname,
                                            "tag":roomtag
                                        }))
                print("room tag task done!")

            ##Bat Migration Blockages
            if task_export_batmigrationblockages_features:
                if len(regiondata["batmigrationblockages"]) > 0:
                    batmigrationblockages_features = []
                    features["batmigrationblockages_features"] = batmigrationblockages_features
                    print("starting bat migration blockages task!")
                    for blockageentry in regiondata["batmigrationblockages"]:
                        if not blockageentry:
                            print("no bat migration entries for current region")
                            blockageentry = ""
                            continue

                        for roomname, room in rooms.items():
                            if blockageentry == roomname:
                                roomcam_min = room['camcoords'][0]
                                roomcam_max = room['camcoords'][0]
                                for camcoords in room['camcoords']:
                                    roomcam_min = np.min([roomcam_min, camcoords],0)
                                    roomcam_max = np.max([roomcam_max, camcoords + camsize],0)
                                popupcoords = (roomcam_max - np.array([((roomcam_max[0] - roomcam_min[0]), 0)])/2).round().tolist()[0]
                                print("bat migration is blocked for room " + blockageentry)
                                batmigrationblockages_features.append(geojson.Feature(
                                    geometry=geojson.Point(np.array(popupcoords).round().tolist()),
                                    properties = {
                                    "room":blockageentry
                                    }))
                else:
                    print("No Entries for " + entry.name)
                print("bat migration blockages task done!")

            ## End
            target = os.path.join(output_folder, slugcat, entry.name)
            if not os.path.exists(target):
                os.makedirs(target, exist_ok=True)
            with open(os.path.join(target, "region.json"), 'w') as myout:
                json.dump(features,myout)
            print("done with features task")

        print("Region done! " + slugcat + "/" + entry.name)

    print("Slugcat done! " + slugcat)

os.makedirs(output_folder, exist_ok=True)
# os.makefile(output_log, exist_ok=True)

# Copy slugcats.json
with open(os.path.join(screenshots_root, "slugcats.json"), "r") as slugcats_from:
    with open(os.path.join(output_folder, "slugcats.json"), "w") as slugcats_to:
        slugcats_to.write(slugcats_from.read())

# Run thru every scug
for slugcat_entry in os.scandir(screenshots_root):
    if slugcat_entry.is_dir():
        do_slugcat(slugcat_entry.name)

print("Done!")
# output_log.write(print().read)
s = input()