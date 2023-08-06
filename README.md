Henpemaz (Original, 1.5):
- [Link to the original 1.5 henpemaz map page](https://henpemaz.github.io/Rain-World-Interactive-Map/index.html)
- [MapExporter](https://github.com/henpemaz/PartModPartMeme/tree/master/MapExporter)
- 
Dual-Iron (1.9 downpour port):
- [Link to the dual-iron 1.9 downpour map page](https://rain-world-map.github.io)
- [MapExporter & generateGeoJSON.py](https://github.com/rain-world-map/generation/releases/latest)
- [msc](https://github.com/rain-world-map/msc)
- [vanilla](https://github.com/rain-world-map/vanilla)
- [front-end app](https://github.com/rain-world-map/rain-world-map.github.io)
- 
JuliaCat (me, 1.9.07b plus):
- [Link to the Experimental 1.9.07b juliacat downpour map page](https://noblecat57.github.io/)
- [Link to the 1.9.07b juliacat downpour map page](https://rain-world-downpour-map.github.io/)
- [MSC 1.9.07b map data](https://github.com/NobleCat57/msc-1.9.07b/tree/v1.9.07b)
- [Vanilla 1.9.07b map data](https://github.com/NobleCat57/vanilla-1.9.07b/tree/v1.9.07b)
- [WIP 1.9.07b generateGeoJSON python script & MapExporter remix mod](https://github.com/NobleCat57/generationPlus/tree/Shortcuts)
  
This project consists of three parts:
- A C# mod, MapExporter, that jumps through the game generating screenshots and exporting metadata about rooms, regions, and maps.
- A python script, generateGeoJSON, that stitches up the screenshots into a map, producing a tileset/basemap and converting the metadata into GeoJSON features. This data is very massive, so it's stored across multiple repositories: MSC for More Slugcats-specific data and Vanilla for survivor, monk, and hunter. Slugbase characters may eventually use their own repos too, if they get added.
- The Front-End App in plain HTML, CSS, and JS using Leaflet for the map. It's all static files so it can be hosted as a GitHub Pages website.

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
- icons for relevant placed objects, like pearls and unlock tokens
- marked room tags like "shelter", "scavoutpost" and "swarmroom"
- tile nodes (+ the yet to be integrated in-room shortcut paths, and then other shortcut types like npc and region transportation)
- bat migration blockages


If you wish to contribute, hmu on Discord!
