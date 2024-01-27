# NOTICE: some of the links here go nowhere because they have not been created yet.
 
 [Link to the map page](https://alduris.github.io/RWModMap/)

This project consists of three parts:
- A C# mod, [MapExporter](https://github.com/alduris/generation/releases/latest), that jumps through the game generating screenshots and exporting metadata about rooms and regions and maps.
- A python script, generateGeoJSON, that stitches up the screenshots into a map, producing a tileset/basemap and converting the metadata into GeoJSON features. This data is very massive, so it's stored across multiple repositories (one for each slugcat, vanilla and msc). Slugbase characters may eventually use their own repos too, if they get added.
- The [front-end app](https://github.com/alduris/RWModMap) in plain HTML, CSS, and JS using Leaflet for the map. It's all static files so it can be hosted as a GitHub Pages website.

To generate assets for the game:
1. Install MapExporter,  run the game, and let the mod do its thing. The game will close when MapExporter is finished.
2. After the game closes, copy the contents of the `exports` folder into a new folder called `py-input`, which should be next to `generateGeoJSON.py`.
3. Run `generateGeoJSON.py`. When it finishes, copy the contents of the `py-output` folder into the `slugcats` folder in the `rain-world-map.github.io` repository. And that's it!

The currently tracked things from the game are:
- room placement from the dev-map
- room names
- room connections
- room geometry
- spawns and lineages
- echoes
- karma gates
- place icons for the most common room tags like "shelter", "scavoutpost" and "swarmroom"
- icons for pearls and unlock tokens

The immediate to-do list for this project is:
- in-room shortcuts
- fixed map placements for rooms that were not placed in dev tools
- fixing memory leaks so everything can be rendered in one big batch

If you wish to contribute, hmu on Discord!
