
using Menu.Remix.MixedUI;
using System;
using System.Collections.Generic;
using UnityEngine;

namespace MapExporter
{
    public class ExporterOptions : OptionInterface
    {
        public override void Initialize()
        {
            base.Initialize();
            this.Tabs = new OpTab[]
            {
                new OpTab(this, "")
            };
            kbUse = new OpKeyBinder(MapExporter.activateKey, new Vector2(100f, 390f), new Vector2(150f, 30f), true, OpKeyBinder.BindController.AnyController);
            checkboxscreenshots = new OpCheckBox(MapExporter.screenshots, new Vector2(105f, 320f))
            {
                description = Translate("Capture Screenshots")
            };
            this.checkboxcamerablacklist = new OpTextBox(MapExporter.cameraBlacklist, new Vector2(350f, 300f), 10f);
            {
                // DefaultCameraBlacklist = ExporterOptions.defaultCameraBlacklist
            };
            this.Tabs[0].AddItems(new UIelement[]
            {
                this.kbUse,
                this.checkboxscreenshots,
                this.checkboxcamerablacklist
            });
            this.checkboxscreenshots.SetNextFocusable(new UIfocusable[]
            {
                this.checkboxscreenshots,
                this.checkboxscreenshots,
                this.checkboxscreenshots,
                this.checkboxscreenshots
            });
            this.checkboxcamerablacklist.SetNextFocusable(new UIfocusable[]
            {
                this.checkboxcamerablacklist,
                this.checkboxcamerablacklist,
                this.checkboxcamerablacklist,
                this.checkboxcamerablacklist
            });
            this.kbUse.SetNextFocusable(new UIfocusable[]
            {
                this.kbUse,
                this.kbUse,
                this.kbUse,
                this.kbUse
            });
            UIfocusable.MutualHorizontalFocusableBind(this.checkboxscreenshots, this.checkboxcamerablacklist);
            UIfocusable.MutualHorizontalFocusableBind(this.kbUse, this.checkboxcamerablacklist);
            UIfocusable.MutualVerticalFocusableBind(this.checkboxscreenshots, this.kbUse);
            this.checkboxscreenshots.SetNextFocusable(UIfocusable.NextDirection.Down, FocusMenuPointer.GetPointer(FocusMenuPointer.MenuUI.RevertButton));
            this.checkboxcamerablacklist.SetNextFocusable(UIfocusable.NextDirection.Down, FocusMenuPointer.GetPointer(FocusMenuPointer.MenuUI.SaveButton));
            OpLabel[] array = new OpLabel[4];
            array[0] = new OpLabel(new Vector2(100f, 430f), new Vector2(200f, 20f), Translate("Screenshots"), FLabelAlignment.Left, false, null)
            {
                description = Translate("Choose a Key to activate GreyScreen ingame"),
                bumpBehav = this.kbUse.bumpBehav
            };
            array[1] = new OpLabel(new Vector2(100f, 350f), new Vector2(200f, 20f), Translate("Capture Specific"), FLabelAlignment.Left, false, null)
            {
                description = Translate("format: \"RA;Slugcat\", \"RA;Slugcat\""),
                bumpBehav = this.checkboxscreenshots.bumpBehav
            };
            array[2] = new OpLabel(new Vector2(300f, 460f), new Vector2(200f, 20f), Translate("Blacklisted Cameras"), FLabelAlignment.Right, false, null)
            {
                description = Translate("By default: { \"SU_B13\", new int[]{2} }, // one indexed, { \"GW_S08\", new int[]{2} }, // in vanilla only, { \"SL_C01\", new int[]{4,5} }, // crescent order or will break"),
                bumpBehav = this.checkboxcamerablacklist.bumpBehav
            };
            this.Tabs[0].AddItems(new UIelement[]
            {
                new OpRect(new Vector2(80f, 40f), new Vector2(440f, 200f), 0.3f)
            });
            string text = "- " + Translate("Press Action Key ingame to toggle masking.");
            text = text + Environment.NewLine + "- " + Translate("If Hide Foreground is checked, GreyScreen will hide terrain completely. Usually gives cleaner results.");
            text = text + Environment.NewLine + "- " + Translate("If Hide Foreground is unchecked, GreyScreen will recolour terrain to the chosen colour. This allows capturing LightSources.");
            text = text + Environment.NewLine + "- " + Translate("Hold Action Key to freeze screen effects. Useful for capturing multi-camera rooms, or optimised GIFs without removing scenery.");
            text = text + Environment.NewLine + "- " + Translate("If the mod is in action, Pause Menu will not darken the screen.");
            array[3] = new OpLabelLong(new Vector2(100f, 60f), new Vector2(400f, 160f), text, true, FLabelAlignment.Left);
            OpTab opTab = this.Tabs[0];
            UIelement[] elements = array;
            opTab.AddItems(elements);
        }

        private OpTextBox checkboxcamerablacklist;
        private OpKeyBinder kbUse;
        private OpCheckBox checkboxscreenshots;

        public static readonly string[] fdefaultCameraBlacklist = new string[]
        {
            "FFFFFF",
            "000000",
        };

        public static readonly string[] paletteName = new string[]
        {
            "White",
            "Black",
        };

        public static string gdefaultCameraBlacklist = "";
    public static readonly Dictionary<string, int[]> defaultCameraBlacklist = new()
    {
        { "SU_B13", new int[]{2} }, // one indexed
        { "GW_S08", new int[]{2} }, // in vanilla only
        { "SL_C01", new int[]{4,5} }, // crescent order or will break
    };


    }
}
