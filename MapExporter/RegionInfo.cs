using System.Collections.Generic;
using UnityEngine;
using System.Text.RegularExpressions;
using System.Linq;
using System.IO;
using RWCustom;

namespace MapExporter;

sealed class RegionInfo : IJsonObject
{
    readonly Dictionary<string, RoomEntry> rooms;
    readonly List<ConnectionEntry> connections;
    readonly string acronym;
    readonly List<Color> fgcolors;
    readonly List<Color> bgcolors;
    readonly List<Color> sccolors;
    readonly HashSet<string> worldConditionalLinks;
    readonly HashSet<string> worldCreatures;
    readonly HashSet<string> worldRoomTags;
    readonly HashSet<string> worldBatMigrationBlockages;

    public string copyRooms;

    public RegionInfo(World world)
    {
        acronym = world.name;

        rooms = new Dictionary<string, RoomEntry>();
        connections = new List<ConnectionEntry>();

        fgcolors = new List<Color>();
        bgcolors = new List<Color>();
        sccolors = new List<Color>();

        worldConditionalLinks = new HashSet<string>();
        worldRoomTags = new HashSet<string>();
        worldCreatures = new HashSet<string>();
        worldBatMigrationBlockages = new HashSet<string>();

        LoadMapConfig(world);
        LoadWorldConfig(world);
    }
    private RoomEntry GetOrCreateRoomEntry(string name)
    {
        return rooms.TryGetValue(name, out var value) ? value : rooms[name] = new(name);
    }

    private void LoadMapConfig(World world)
    {
        string path = AssetManager.ResolveFilePath(
            $"World{Path.DirectorySeparatorChar}{world.name}{Path.DirectorySeparatorChar}map_{world.name}-{world.game.GetStorySession.saveState.saveStateNumber}.txt"
            );

        if (!File.Exists(path))
        {
            path = AssetManager.ResolveFilePath(
                $"World{Path.DirectorySeparatorChar}{world.name}{Path.DirectorySeparatorChar}map_{world.name}.txt"
                );
        }

        if (!File.Exists(path))
        {
            MapExporter.Logger.LogWarning($"No map data for {world.game.StoryCharacter}/{world.name} at {path}");
        }
        else
        {
            MapExporter.Logger.LogDebug($"Found map data for {world.game.StoryCharacter}/{world.name} at {path}");

            string[] contents = File.ReadAllLines(path);

            foreach (string s in contents)
            {
                string[] split = Regex.Split(s, ": ");
                string sname = split[0];

                if (sname == "Connection")
                {
                    connections.Add(new ConnectionEntry(split[1]));
                }
                else if (!MapExporter.HiddenRoom(world.GetAbstractRoom(sname)))
                {
                    GetOrCreateRoomEntry(sname).ParseEntry(split[1]);
                }
            }
        }
    }

    private void LoadWorldConfig(World world)
    {
        string acronym = world.region.name;
        string path = AssetManager.ResolveFilePath($"world/{acronym}/world_{acronym}.txt");
        if (File.Exists(path))
        {
            AssimilateConditionalLinks(File.ReadAllLines(path));
            AssimilateRoomTags(File.ReadAllLines(path));
            AssimilateCreatures(File.ReadAllLines(path));
            AssimilateBatMigrationBlockages(File.ReadAllLines(path));
        }
        else
        {
            MapExporter.Logger.LogError($"WORLD FILE DOES NOT EXIST: {path}");
        }
    }

    private void AssimilateConditionalLinks(IEnumerable<string> raw)
    {
        bool insideofconditionallinks = false;
        foreach (var item in raw)
        {
            if (item == "CONDITIONAL LINKS") insideofconditionallinks = true;
            else if (item == "END CONDITIONAL LINKS") insideofconditionallinks = false;
            else if (insideofconditionallinks)
            {
                if (string.IsNullOrEmpty(item) || item.StartsWith("//")) continue;
                worldConditionalLinks.Add(item);
            }
        }
    }
    private void AssimilateRoomTags(IEnumerable<string> raw)
    {
        bool insideofrooms = false;
        foreach (var item in raw)
        {
            if (item == "ROOMS") insideofrooms = true;
            else if (item == "END ROOMS") insideofrooms = false;
            else if (insideofrooms)
            {
                if (string.IsNullOrEmpty(item) || item.StartsWith("//")) continue;
                worldRoomTags.Add(item);
            }
        }
    }
    private void AssimilateCreatures(IEnumerable<string> raw)
    {
        bool insideofcreatures = false;
        foreach (var item in raw)
        {
            if (item == "CREATURES") insideofcreatures = true;
            else if (item == "END CREATURES") insideofcreatures = false;
            else if (insideofcreatures)
            {
                if (string.IsNullOrEmpty(item) || item.StartsWith("//")) continue;
                worldCreatures.Add(item);
            }
        }
    }
    private void AssimilateBatMigrationBlockages(IEnumerable<string> raw)
    {
        bool insideofbatmigration = false;
        foreach (var item in raw)
        {
            if (item == "BAT MIGRATION BLOCKAGES") insideofbatmigration = true;
            else if (item == "END BAT MIGRATION BLOCKAGES") insideofbatmigration = false;
            else if (insideofbatmigration)
            {
                if (string.IsNullOrEmpty(item) || item.StartsWith("//")) continue;
                worldBatMigrationBlockages.Add(item);
            }
        }
    }

    static float[] Vec2arr(Vector2 vec) => new float[] { vec.x, vec.y };
    static float[] Vec2arr(Vector3 vec) => new float[] { vec.x, vec.y, vec.z };
    static int[] Intvec2arr(IntVector2 vec) => new int[] { vec.x, vec.y };

    public void UpdateRoom(Room room)
    {
        GetOrCreateRoomEntry(room.abstractRoom.name).UpdateEntry(room);
    }

    public Dictionary<string, object> ToJson()
    {
        var ret = new Dictionary<string, object>
        {
            ["acronym"] = acronym,
            ["fgcolors"] = (from s in fgcolors select Vec2arr((Vector3)(Vector4)s)).ToList(),
            ["bgcolors"] = (from s in bgcolors select Vec2arr((Vector3)(Vector4)s)).ToList(),
            ["sccolors"] = (from s in sccolors select Vec2arr((Vector3)(Vector4)s)).ToList()
        };
        if (copyRooms == null)
        {
            ret["rooms"] = rooms;
            ret["connections"] = connections;
        }
        else
        {
            ret["copyRooms"] = copyRooms;
        }
        ret["conditionallinks"] = worldConditionalLinks.ToArray();
        ret["roomtags"] = worldRoomTags.ToArray();
        ret["creatures"] = worldCreatures.ToArray();
        ret["batmigrationblockages"] = worldBatMigrationBlockages.ToArray();
        return ret;
    }

    internal void LogPalette(RoomPalette currentPalette)
    {
        // get sky color and fg color (px 00 and 07)
        Color fg = currentPalette.texture.GetPixel(0, 0);
        Color bg = currentPalette.texture.GetPixel(0, 7);
        Color sc = currentPalette.shortCutSymbol;
        fgcolors.Add(fg);
        bgcolors.Add(bg);
        sccolors.Add(sc);
    }

    sealed class RoomEntry : IJsonObject
    {
        public string roomName;

        public RoomEntry(string roomName)
        {
            this.roomName = roomName;
        }

        // from map txt
        public Vector2 devPos;
        public Vector2 canPos;
        public int canLayer;
        public string subregion;
        public bool everParsed = false;
        public void ParseEntry(string entry)
        {
            string[] fields = Regex.Split(entry, "><");
            canPos.x = float.Parse(fields[0]);
            canPos.y = float.Parse(fields[1]);
            devPos.x = float.Parse(fields[2]);
            devPos.y = float.Parse(fields[3]);
            canLayer = int.Parse(fields[4]);
            subregion = fields[5];
            everParsed = true;
        }

        // from room
        public Vector2[] cameras; // TODO: can this cause issues if it's not the same as the cache?
        private int[] size;
        private int[,][] tiles;
        private IntVector2[] nodes;
        private IntVector2[] shortcuts;

        public void UpdateEntry(Room room)
        {
            cameras = room.cameraPositions;

            size = new int[] { room.Width, room.Height };

            tiles = new int[room.Width, room.Height][];
            for (int k = 0; k < room.Width; k++)
            {
                for (int l = 0; l < room.Height; l++)
                {
                    // Dont like either available formats ?
                    // Invent a new format
                    tiles[k, l] = new int[] { (int)room.Tiles[k, l].Terrain, (room.Tiles[k, l].verticalBeam ? 2 : 0) + (room.Tiles[k, l].horizontalBeam ? 1 : 0), (int)room.Tiles[k, l].shortCut };
                    //terain, vb+hb, sc
                }
            }
            nodes = room.exitAndDenIndex;
            shortcuts = room.shortcutsIndex;
        }

        // wish there was a better way to do this
        public Dictionary<string, object> ToJson()
        {
            return new Dictionary<string, object>()
            {
                { "roomName", roomName },
                { "canPos", Vec2arr(canPos) },
                { "canLayer", canLayer },
                { "devPos", Vec2arr(devPos) },
                { "subregion", subregion },
                { "cameras", cameras != null ? (from c in cameras select Vec2arr(c)).ToArray() : null},
                { "nodes", nodes != null ? (from n in nodes select Intvec2arr(n)).ToArray() : null},
                { "shortcuts", shortcuts != null ? (from n in nodes select Intvec2arr(n)).ToArray() : null},
                { "size", size},
                { "tiles", tiles},
            };
        }
    }

    sealed class ConnectionEntry : IJsonObject
    {
        public string roomA;
        public string roomB;
        public IntVector2 posA;
        public IntVector2 posB;
        public int dirA;
        public int dirB;

        public ConnectionEntry(string entry)
        {
            string[] fields = Regex.Split(entry, ",");
            roomA = fields[0];
            roomB = fields[1];
            posA = new IntVector2(int.Parse(fields[2]), int.Parse(fields[3]));
            posB = new IntVector2(int.Parse(fields[4]), int.Parse(fields[5]));
            dirA = int.Parse(fields[6]);
            dirB = int.Parse(fields[7]);
        }

        public Dictionary<string, object> ToJson()
        {
            return new Dictionary<string, object>()
            {
                { "roomA", roomA },
                { "roomB", roomB },
                { "posA", Intvec2arr(posA) },
                { "posB", Intvec2arr(posB) },
                { "dirA", dirA },
                { "dirB", dirB },
            };
        }
    }
}
