import bpy
from bpy.props import FloatProperty, IntProperty

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
        # TODO: Add Property 'Default Intensity' and default to 3.41

class OBJECT_OT_BakeLightmaps(bpy.types.Operator):
    """Bake Lightmaps for selected objects"""
    bl_idname = "object.bake_lightmaps"
    bl_label = "Bake Lightmaps"

    default_intensity: FloatProperty(
        name = "Lightmaps Intensity",
        default = 3.14
    )

    resolution: IntProperty(
        name = "Lightmaps Resolution",
        default = 2048
    )

    samples: IntProperty(
        name = "Max Samples",
        default = 2048
    )

    def execute(self, context):
        # Check selected objects
        selected_objects = bpy.context.selected_objects
        # Filter mesh objects
        mesh_objs = [ob for ob in selected_objects if ob.type == 'MESH']

        # set up UV layer structure. The first layer has to be UV0, the second one UV1 for the lightmap
        for obj in mesh_objs:
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
        # TODO: We need to warn the user at some place like the README that the uv_layer[1] gets completely overwritten if it is called 'UV1'
        bpy.ops.uv.lightmap_pack()
        bpy.ops.object.mode_set(mode='OBJECT')

        # Gather all materials on the selected objects
        materials = []
        for obj in mesh_objs:
            # TODO: Make more efficient
            for slot in obj.material_slots:
                if slot.material not in materials:
                    materials.append(slot.material)
        # Check for the required nodes and set them up if not present
        lightmap_texture_nodes = []
        for mat in materials:
            mat_nodes = mat.node_tree.nodes
            lightmap_nodes = [node for node in mat_nodes if node.bl_idname=='moz_lightmap.node']
            if len(lightmap_nodes) > 1:
                print("Too many lightmap nodes in node tree of material", mat.name)
            elif len(lightmap_nodes) < 1:
                lightmap_texture_nodes.append(self.setup_moz_lightmap_nodes(mat.node_tree))
            else:
                # TODO: Check wether all nodes are set up correctly, for now assume they are
                lightmap_nodes[0].intensity = self.default_intensity
                # the image texture node needs to be the active one for baking, it is connected to the lightmap node so get it from there
                lightmap_texture_node = lightmap_nodes[0].inputs[0].links[0].from_node
                mat.node_tree.nodes.active = lightmap_texture_node
                lightmap_texture_nodes.append(lightmap_texture_node)

        # Baking has to happen in Cycles, it is not supported in EEVEE yet
        render_engine_tmp = context.scene.render.engine
        context.scene.render.engine = 'CYCLES'
        samples_tmp = context.scene.cycles.samples
        context.scene.cycles.samples = self.samples
        # Baking needs to happen without the color pass because we only want the direct and indirect light contributions
        bake_settings = context.scene.render.bake
        bake_settings.use_pass_direct = True
        bake_settings.use_pass_indirect = True
        bake_settings.use_pass_color = False
        # The should be small because otherwise it could overwrite UV islands
        bake_settings.margin = 1
        # Not sure whether this has any influence
        bake_settings.image_settings.file_format = 'HDR'
        context.scene.render.image_settings.file_format = 'HDR'
        bpy.ops.object.bake(type='DIFFUSE')
        # After baking is done, return everything back to normal
        context.scene.cycles.samples = samples_tmp
        context.scene.render.engine = render_engine_tmp
        # Pack all newly created or updated images
        for node in lightmap_texture_nodes:
            # file_path = bpy.path.abspath("//"+node.image.name+".hdr")
            # node.image.save_render(file_path)
            node.image.file_format = 'HDR'
            node.image.pack()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # needed to get the dialoge with the intensity
        return context.window_manager.invoke_props_dialog(self)
    
    def setup_moz_lightmap_nodes(self, node_tree):
        ''' Returns the lightmap texture node of the newly created setup '''
        mat_nodes = node_tree.nodes
        # This function gets called when no lightmap node is present
        lightmap_node = mat_nodes.new(type="moz_lightmap.node")
        lightmap_node.intensity = self.default_intensity

        lightmap_texture_node = mat_nodes.new(type="ShaderNodeTexImage")
        lightmap_texture_node.location[0] -= 300

        img = bpy.data.images.new('LightMap', self.resolution, self.resolution, alpha=False, float_buffer=True)
        lightmap_texture_node.image = img

        UVmap_node = mat_nodes.new(type="ShaderNodeUVMap")
        UVmap_node.uv_map = "UV1"
        UVmap_node.location[0] -= 500

        node_tree.links.new(UVmap_node.outputs['UV'], lightmap_texture_node.inputs['Vector'])
        node_tree.links.new(lightmap_texture_node.outputs['Color'], lightmap_node.inputs['Lightmap'])

        # the image texture node needs to be the active one for baking
        node_tree.nodes.active = lightmap_texture_node

        return lightmap_texture_node


def register():
    bpy.utils.register_class(HubsPanel)
    bpy.utils.register_class(OBJECT_OT_BakeLightmaps)

def unregister():
    bpy.utils.unregister_class(HubsPanel)
    bpy.utils.unregister_class(OBJECT_OT_BakeLightmaps)

if __name__ == "__main__":
    register()