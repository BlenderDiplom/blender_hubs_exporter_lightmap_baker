import bpy

bl_info = {
    "name": "Hubs Lightmap Baker",
    "author": "BlenderDiplom",
    "description": "Tools for automatically baking lightmaps to be used with the Blender hubs exporter.",
    "blender": (3, 6, 0),
    "version": (0, 1, 0, "alpha_build"),
    "location": "Object Properties -> Hubs Lightmap Baker",
    "wiki_url": "",
    "tracker_url": "",
    "support": "COMMUNITY",
    "warning": "Requires the Hubs Blender exporter add-on to work.",
    "category": "Generic"
}

# TODO: Add a check whether the io_hubs_addon is installed and actived in the preferences 
# https://blender.stackexchange.com/questions/43703/how-to-tell-if-an-add-on-is-present-using-python

class HubsPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Hubs Lightmap Baker"
    bl_idname = "OBJECT_PT_hubs"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator("object.bake_lightmaps", text="Bake Lightmaps of selected objects")
        # TODO: Add Property 'Intensity' and default to 3.41

class OBJECT_OT_BakeLightmaps(bpy.types.Operator):
    """Bake Lightmaps for selected objects"""
    bl_idname = "object.bake_lightmaps"
    bl_label = "Bake Lightmaps"

    def execute(self, context):
        # Check selected objects
        selected_objects = bpy.context.selected_objects

        # set up UV layer structure. The first layer has to be UV0, the second one UV1 for the lightmap
        for obj in selected_objects:
            if obj.type == 'MESH':
                obj_uv_layers = obj.data.uv_layers
                # Check whether there are any UV layers and if not, create the two that are required
                if len(obj_uv_layers) == 0:
                    obj_uv_layers.new(name='UV0')
                    obj_uv_layers.new(name='UV1')
                # The first layer is usually used for regular texturing so don't touch it, just rename it.
                # Check if object has a first UV layer named "UV0"
                elif obj_uv_layers[0].name != 'UV0':
                    # Rename the first UV layer to "UV0"                    
                    obj_uv_layers[0].name = 'UV0'

                if len(obj_uv_layers) == 1:
                    obj_uv_layers.new(name='UV1')
                # Check if object has a second UV layer named "UV1"
                elif obj_uv_layers[1].name != 'UV1':
                    print("The second UV layer in hubs should be named UV1 and is reserved for the lightmap, all the layers >1 are ignored.")
                    obj_uv_layers.new(name='UV1')
                    # The new layer is the last in the list, swap it for position 1
                    obj_uv_layers[1], obj_uv_layers[-1] = obj_uv_layers[-1], obj_uv_layers[1]

                # The layer for the lightmap needs to be the active one before lightmap packing
                obj_uv_layers.active = obj_uv_layers['UV1']

        # run UV lightmap packing on all selected objects
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.lightmap_pack()

        # TODO: Gather all materials on the selected objects
        # TODO: For each material, check wether a node of type 'MOZ_lightmap settings' is present and if yes, check whether it is wired correctly
        # TODO: If that node is not present, add such a node, an image texture node and a UV Map node and wire them correctly    

        return {'FINISHED'}

def register():
    bpy.utils.register_class(HubsPanel)
    bpy.utils.register_class(OBJECT_OT_BakeLightmaps)

def unregister():
    bpy.utils.unregister_class(HubsPanel)
    bpy.utils.unregister_class(OBJECT_OT_BakeLightmaps)

if __name__ == "__main__":
    register()