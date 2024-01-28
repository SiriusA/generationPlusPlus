from copy import copy
import os
import json, geojson
import statistics
import colorsys
import numpy as np
from PIL import Image

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

screenshots_root = "./py-input"
output_folder = "./py-output"

optimize_geometry = True
skip_existing_tiles = True
only_slugcat = None
only_region = None

task_export_tiles = True
task_export_features = True
task_export_room_features = True
task_export_connection_features = True
task_export_geo_features = True
task_export_spawn_features = True

def do_slugcat(slugcat: str):
    if only_slugcat is not None and only_slugcat != slugcat:
        return

    print("Found slugcat regions: " + slugcat)
        
    for entry in os.scandir(os.path.join(screenshots_root, slugcat)):
        if not entry.is_dir() or len(entry.name) != 2 or (only_region is not None and only_region != entry.name):
            continue

        print("Found region: " + entry.name)
        with open(os.path.join(entry.path, "metadata.json")) as metadata:
            regiondata = json.load(metadata)
        assert entry.name == str(regiondata['acronym']).lower()

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
            # find good contrastign color
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
        
            ## Spawns
            if task_export_spawn_features:
                spawn_features = []
                features["spawn_features"] = spawn_features
                print("creatures task!")
                # read spawns, group spawns into dens (dens have a position)
                dens = {}
                for spawnentry in regiondata["spawns"]:
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
                    

                    # homemade patch to support CRS conditionals, woohoo
                    if spawnentry.startswith("{"):
                        # skip until the end
                        spawnentry = spawnentry[spawnentry.index("}")+1:]

                    arr = spawnentry.split(" : ")
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
                        # TODO read creature attributes
                        spawn["lineage_probs"] = [creature.split("-")[-1] for creature in creature_arr]
                        spawn["creature"] = spawn["lineage"][0]
                        spawn["amount"] = 1
                        spawn["pre_cycle"] = "{PreCycle}" in arr[3]
                        spawn["night"] = "{Night}" in arr[3]

                        denkey = arr[1]+ ":" +arr[2] # room:den
                        if denkey in dens:
                            dens[denkey]["spawns"].append(spawn)
                        else:
                            dens[denkey] = {"room":arr[1],"den":int(arr[2]),"spawns":[spawn]}
                    else:
                        creature_arr = arr[1].split(", ")
                        room_name = arr[0]
                        for creature_desc in creature_arr:
                            spawn = {}
                            spawn["is_lineage"] = False
                            spawn["pre_cycle"] = False
                            spawn["night"] = False
                            den_index,spawn["creature"], *attr = creature_desc.split("-")

                            if room_name  != "OFFSCREEN" and room_name not in rooms:
                                # creature is in a room that doesn't exist for this region
                                continue
                            if room_name  != "OFFSCREEN" and not den_index.isdigit():
                                print("faulty spawn! den index missing in room name: " + room_name + " : " + creature_desc)
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
                        
                            spawn["amount"] = 1
                            if attr:
                                # TODO read creature attributes
                                if not attr[-1].endswith("}"):
                                    try:
                                        spawn["amount"] = int(attr[-1])
                                    except:
                                        print("amount not specified. first attribute is \"" + attr[-1] + "\" in \"" + room_name + " : " + creature_desc + "\"")
                                if "{PreCycle}" in attr:
                                    spawn["pre_cycle"] = True
                                if "{Night}" in attr:
                                    spawn["night"] = True

                            if spawn["creature"] == "Spider 10": ## Bruh...
                                print("faulty spawn! stupid spiders: " + room_name + " : " + creature_desc)
                                continue ## Game doesnt parse it, so wont I
                            denkey = room_name+ ":" +den_index # room:den
                            if denkey in dens:
                                dens[denkey]["spawns"].append(spawn)
                            else:
                                dens[denkey] = {"room":room_name,"den":int(den_index),"spawns":[spawn]}
                ## process dens into features
                for _,den in dens.items():
                    if den["room"] == "OFFSCREEN":
                        if not 'offscreen' in regiondata:
                            print("notice: created OffScreenDen_" + entry.name.upper())
                            regiondata['offscreen'] = {'roomName': 'OffScreenDen_' + entry.name.upper(), 'canPos': [0, 0], 'canLayer': 1, 'devPos': [0, 0], 'subregion': '', 'cameras': None, 'nodes': None, 'size': None, 'tiles': None, 'roomcoords': [0, 0], 'camcoords': None}
                        room = regiondata['offscreen']
                        dencoords = room['roomcoords'] + ofscreensize/2
                    else:
                        room = rooms[den["room"]]
                        dencoords = room['roomcoords'] + center_of_tile + 20* np.array(room['nodes'][den["den"]])
                    spawn_features.append(geojson.Feature(
                        geometry=geojson.Point(np.array(dencoords).round().tolist()),
                        properties=den))

                print("creatures task done!")

            target = os.path.join(output_folder, slugcat, entry.name)
            if not os.path.exists(target):
                os.makedirs(target, exist_ok=True)
            with open(os.path.join(target, "region.json"), 'w') as myout:
                json.dump(features,myout)
            print("done with features task")

        print("Region done! " + entry.name)

    print("Slugcat done! " + slugcat)

os.makedirs(output_folder, exist_ok=True)

# Copy slugcats.json
with open(os.path.join(screenshots_root, "slugcats.json"), "r") as slugcats_from:
    with open(os.path.join(output_folder, "slugcats.json"), "w") as slugcats_to:
        slugcats_to.write(slugcats_from.read())

# Run thru every scug
for slugcat_entry in os.scandir(screenshots_root):
    if slugcat_entry.is_dir():
        do_slugcat(slugcat_entry.name)

print("Done!")
s = input()
