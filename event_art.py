"""Thematic narrative art; distinct from interactive minigame backgrounds."""
GROUPS={
'wounded':'wounded sharp_wire',
'wreck':'wreck',
'camp':'camp hermit lesson field_tailor gun_oil',
'mines':'mines warning_flags glass_dune cemetery',
'signal':'signal broken_radio',
'pilgrims':'pilgrims scrap_buyer plate_buyer donation',
'provisions':'berries aidbox pantry beehive copper_wire buried_battery roof_cache fallen_tree spoiled_can torn_pocket',
'snare':'snare lost_dog',
'safe':'safe clean_cache locked_armory locked_workshop locked_provisions locked_research',
'pharmacy':'pharmacy locked_locker locked_medical',
'terminal':'terminal dust_archive old_survey',
'courier':'courier',
'toll':'toll',
'storm':'storm toxic_air sand_lock',
'meteor':'meteor bunker_light',
'water':'water_filter clean_spring'}
EVENT_ART={event:'event_theme:'+theme for theme,events in GROUPS.items() for event in events.split()}

# New road events reuse the closest existing narrative illustration.
EVENT_ART.update({event:"event_theme:"+theme for theme,events in {
"water":"rain_collector leaking_roof", "signal":"signal_kites sun_mirror", "provisions":"mushroom_bed cloth_bundle broken_cart", "terminal":"frozen_terminal civic_archive", "mines":"cracked_bridge thorn_patch collapsed_stairs", "pharmacy":"medicine_exchange", "wreck":"sand_cable workshop_press", "courier":"courier_tip", "camp":"old_trapper quiet_clearing", "storm":"ash_whirl rad_markers"}.items() for event in events.split()})
