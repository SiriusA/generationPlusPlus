using IL.JollyCoop;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;

namespace MapExporter;

static class ReusedRooms
{
    struct RegionData
    {
        public Dictionary<string, RoomSettings> settings;
    }

    static readonly Dictionary<string, RegionData> regions = new();
    static readonly List<string> dessicatedRegionList = new();

    public static void saveReusedRooms(string path)
    {

        Dictionary<string, Dictionary<string, string>> baseSlugWorldToRooms = new Dictionary<string, Dictionary<string, string>>();
        MapExporter.Logger.LogDebug($"regions: {regions}");
        MapExporter.Logger.LogDebug($"regions keys: {regions.Keys}");
        foreach (string baseSlugWorld in regions.Keys)
        {
            if (!dessicatedRegionList.Contains(baseSlugWorld))
            {
                MapExporter.Logger.LogDebug($"adding to reusedRoomst: {baseSlugWorld}");
                dessicatedRegionList.Add(baseSlugWorld);
            }
        }

        //TODO: could probably replace with txt files instead... 
        string output = Json.Serialize(dessicatedRegionList);
        MapExporter.Logger.LogDebug($"ReusedRoom output: {output}");
        File.WriteAllText(path, output);
    }

    public static void loadReusedRooms(string path)
    {
        try
        {
            //TODO: could probably replace with txt files instead... 
            string input = File.ReadAllText(path);
            List<object> dessicatedLoadedO = Json.Deserialize(input) as List<object>;
            foreach (object baseSlugWorld in dessicatedLoadedO)
            {
                dessicatedRegionList.Add(baseSlugWorld.ToString());
            }
        } catch (System.Exception e)
        {
            MapExporter.Logger.LogWarning($"Unable to load reusedRooms. exception: {e}");
        }
        MapExporter.Logger.LogInfo("Loaded dehydrated reusedRooms");
    }

    public static string SlugcatRoomsToUse(string slugcat, World world, List<AbstractRoom> validRooms, RainWorldGame game)
    {
        slugcat = slugcat.ToLower();

        string baseSlugcat = SlugcatFor(slugcat, world.name);
        string key = $"{baseSlugcat}#{world.name}";

        MapExporter.Logger.LogDebug($"slugcat: {slugcat} baseSlugCat: {baseSlugcat}");
        if (baseSlugcat == slugcat) {
            regions[key] = new() {
                settings = validRooms.ToDictionary(
                    keySelector: a => a.name,
                    elementSelector: Settings,
                    comparer: System.StringComparer.InvariantCultureIgnoreCase
                    )
            };
            MapExporter.Logger.LogDebug($"added {key} to regions");
            return null;
        }
        if (!regions.TryGetValue(key, out RegionData regionData)) {
            if (dessicatedRegionList.Contains(key))
            {
                // Rehydrate the region for the base slugcat.
                SlugcatStats.Name baseSlugCatEnum = new(baseSlugcat);
                game.overWorld.LoadWorld(world.name, baseSlugCatEnum, false);

                List<AbstractRoom> rooms = game.world.abstractRooms.ToList();

                // Don't image rooms not available for this slugcat
                rooms.RemoveAll(MapExporter.HiddenRoom);

                // Don't image offscreen dens
                rooms.RemoveAll(r => r.offScreenDen);

                regions[key] = new()
                {
                    settings = rooms.ToDictionary(
                    keySelector: a => a.name,
                    elementSelector: Settings,
                    comparer: System.StringComparer.InvariantCultureIgnoreCase
                    )
                };
                regionData = regions[key];

                SlugcatStats.Name slugCatEnum = new(slugcat);
                game.overWorld.LoadWorld(world.name, slugCatEnum, false);
            }
            else
            {
                MapExporter.Logger.LogWarning($"NOT COPIED | Region settings are not stored for {baseSlugcat}/{world.name} coming from {slugcat}");
                return null;
            }
        }
        if (regionData.settings.Count != validRooms.Count) {
            MapExporter.Logger.LogWarning($"NOT COPIED | Different room count for {world.name} in {baseSlugcat} and {slugcat}");
            return null;
        }
        foreach (AbstractRoom room in validRooms) {
            if (!regionData.settings.TryGetValue(room.name, out RoomSettings existingSettings)) {
                MapExporter.Logger.LogWarning($"NOT COPIED | The room {room.name} exists for {slugcat} but not {baseSlugcat}");
                return null;
            }
            if (!Identical(existingSettings, Settings(room))) {
                MapExporter.Logger.LogWarning($"NOT COPIED | The room {room.name} is different for {slugcat} and {baseSlugcat}");
                return null;
            }
        }
        MapExporter.Logger.LogDebug($"Copying rooms from {baseSlugcat} to {slugcat}/{world.name}");
        return baseSlugcat;

        // EXCLUDE HIDDEN ROOMS.
        // if number of rooms is different, null
        // if room name from one is missing from the other, null
        // if any room's settings differ, null
        // else, baseSlugcat
    }

    private static RoomSettings Settings(AbstractRoom a) => new(a.name, a.world.region, false, false, a.world.game.StoryCharacter);

    public static string SlugcatFor(string slugcat, string region)
    {
        region = region.ToLower();
        if (region is "lc" or "lm" || region is "gw" && slugcat == "spear")
            return "artificer";
        if (region is "cl" or "ug")
            return "saint";
        if (region is "rm")
            return "rivulet";
        return "white";
    }

    static bool Identical(RoomSettings one, RoomSettings two)
    {
        if (ReferenceEquals(one, two)) {
            return true;
        }
        if (one.name.StartsWith("GATE") && two.name.StartsWith("GATE")) {
            // This is a hack to fix gates. For some reason gates and gates *specifically* change constantly between slugcats.
            return true;
        }
        if (one == null || two == null) {
            return false;
        }
        bool p1 = one.isAncestor == two.isAncestor && one.isTemplate == two.isTemplate && one.clds == two.clds && one.swAmp == two.swAmp && one.swLength == two.swLength &&
            one.wAmp == two.wAmp && one.wetTerrain == two.wetTerrain && one.eColA == two.eColA && one.eColB == two.eColB && one.grm == two.grm && one.pal == two.pal &&
            one.wtrRflctAlpha == two.wtrRflctAlpha;
        if (!p1) {
            return false;
        }
        bool fadePalettesMatch = one.fadePalette == null && two.fadePalette == null ||
            one.fadePalette != null && two.fadePalette != null && one.fadePalette.palette == two.fadePalette.palette && one.fadePalette.fades.SequenceEqual(two.fadePalette.fades);
        if (!fadePalettesMatch) {
            return false;
        }
        bool effectsMatch = one.effects.Select(e => e.ToString()).SequenceEqual(two.effects.Select(e => e.ToString()));
        if (!effectsMatch) {
            return false;
        }
        bool placedObjectsMatch = one.placedObjects.Select(p => p.ToString()).SequenceEqual(two.placedObjects.Select(p => p.ToString()));
        if (!placedObjectsMatch) {
            return false;
        }
        return Identical(one.parent, two.parent);
    }
}
