using System.Collections.Generic;
using UnityEngine;
using System.Text.RegularExpressions;
using System.Linq;
using System.IO;
using RWCustom;
using AssemblyCSharp;
using System.Collections.Generic;
using System.Globalization;
using System.IO;

namespace MapExporter;

sealed class RoomInfo : IJsonObject
{
    readonly string acronym;
    readonly HashSet<string> worldRoomSettings;
    readonly HashSet<string> worldRoomName;

    public RoomInfo(World world, AbstractRoom room)
    {
        acronym = world.name;
        worldRoomSettings = new HashSet<string>();
        worldRoomName = new HashSet<string>();
        LoadRoomConfig(world, room);
    }
    
    public void LoadRoomConfig(World world, AbstractRoom room)
    {
        string path = AssetManager.ResolveFilePath(
            $"World{Path.DirectorySeparatorChar}{world.name}{Path.DirectorySeparatorChar}{world.name}-rooms{Path.DirectorySeparatorChar}{room.name}_settings-{world.game.GetStorySession.saveState.saveStateNumber}.txt"
            );

        if (!File.Exists(path)) {
            MapExporter.Logger.LogWarning($"No specific room data for {world.game.StoryCharacter}/{room.name} at {path}");
            path = AssetManager.ResolveFilePath(
                $"World{Path.DirectorySeparatorChar}{world.name}{Path.DirectorySeparatorChar}{world.name}-rooms{Path.DirectorySeparatorChar}{room.name}_settings.txt"
                );
            if (!File.Exists(path)) {
                MapExporter.Logger.LogWarning($"No generic room data for {world.game.StoryCharacter}/{room.name} at {path}");
                path = AssetManager.ResolveFilePath(
                    $"World{Path.DirectorySeparatorChar}{world.name}{Path.DirectorySeparatorChar}{world.name}-gates{Path.DirectorySeparatorChar}{room.name}_settings-{world.game.GetStorySession.saveState.saveStateNumber}.txt"
                    );
                if (!File.Exists(path)) {
                    MapExporter.Logger.LogWarning($"No specific gate data for {world.game.StoryCharacter}/{room.name} at {path}");
                    path = AssetManager.ResolveFilePath(
                        $"World{Path.DirectorySeparatorChar}{world.name}{Path.DirectorySeparatorChar}{world.name}-gates{Path.DirectorySeparatorChar}{room.name}_settings.txt"
                        );
                    if (!File.Exists(path)) {
                        MapExporter.Logger.LogDebug($"No generic gate data for {world.game.StoryCharacter}/{room.name} at {path}");
                    }
                    else {
                        MapExporter.Logger.LogDebug($"Found generic gate data for {world.game.StoryCharacter}/{room.name} at {path}");
                        string[] genericgatedata = File.ReadAllLines(path);
                        string roomName = room.name;
                        AssimilateRoomSettings(genericgatedata, roomName);
                    }
                }
                else {
                    MapExporter.Logger.LogDebug($"Found specific gate date for {world.game.StoryCharacter}/{room.name} at {path}");
                    string[] specificgatedata = File.ReadAllLines(path);
                    string roomName = room.name;
                    AssimilateRoomSettings(specificgatedata, roomName);
                }
            }
            else {
                MapExporter.Logger.LogDebug($"Found generic room date for {world.game.StoryCharacter}/{room.name} at {path}");
                string[] genericroomdata = File.ReadAllLines(path);
                string roomName = room.name;
                AssimilateRoomSettings(genericroomdata, roomName);
            }
        }
        else {
            MapExporter.Logger.LogDebug($"Found specific room data for {world.game.StoryCharacter}/{room.name} at {path}");  
            string[] specificroomdata = File.ReadAllLines(path);
            string roomName = room.name;
            AssimilateRoomSettings(specificroomdata, roomName);
        }
    }

    public void AssimilateRoomSettings(IEnumerable<string> raw, string roomName)
    {
        bool insideofplacedobjects = false;
        foreach (var item in raw)
        {
            if (item.StartsWith("PlacedObjects: ")) insideofplacedobjects = true;
            else if (item.StartsWith("AmbientSounds: ")) insideofplacedobjects = false;
            else if (insideofplacedobjects)
            {
                if (string.IsNullOrEmpty(item) || item.StartsWith("//")) continue;
                worldRoomSettings.Add(item);
            }
        }
        worldRoomName.Add(roomName);
    }

    public Dictionary<string, object> ToJson()
    {
        var ret = new Dictionary<string, object> {
            ["acronym"] = acronym
        };
        ret["roomname"] = worldRoomName.ToArray();
        ret["placedobjects"] = worldRoomSettings.ToArray();
        return ret;
    }
}
