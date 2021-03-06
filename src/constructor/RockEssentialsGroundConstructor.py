import bpy
import os

from src.loader.Loader import Loader
from src.utility.Config import Config
from src.utility.Utility import Utility


class RockEssentialsGroundConstructor(Loader):
    """

    **Ground plane properties**:

    .. csv-table::
       :header: "Keyword", "Description"

       "shader_path", "Path to a .blend file that containing PBR Rock Shader in //NodeTree// section. Type: string."
       "plane_scale", "Scale of a ground plane. Type: mathutils Vector/list. Optional. Default value: [10, 10, 1]"
       "subdivision_cuts", "Amount of cuts along each plane axis. Type: int. Optional. Default value: 50."
       "subdivision_render_levels", "Render level for a plane's subdivision modifier. Type: int. Optional. Default value: 3."
       "displacement_strength", "Strength of a plane's displacement modifier. Type: float. Optional. Default value: 1."
       "tile_name", "Name of the ground tile. Set one if you plan to use this module multiple times in one config. Optional. Type: string. Default_value: 'RE_ground_plane'."
       "AO", "AO color vector ([R, G, B, A]) for a ground shader. Optional. Type: list. Default value: [1, 1, 1, 1]."
    """

    def __init__(self, config):
        Loader.__init__(self, config)

    def run(self):
        """ Constructs ground plane. """

        tiles = self.config.get_list("tiles", [])
        for tile in tiles:
            if tile:
                ground_config = Config(tile)
                self._load_shader(ground_config)
                self._construct_ground_plane(ground_config)

    def _load_shader(self, ground_config):
        """ Loads PBR Rock Shader

        :param ground_config: Config object that contains user-defined settings for ground plane.
        """
        shader_path = ground_config.get_string("shader_path")
        bpy.ops.wm.append(filepath=os.path.join(shader_path, "/NodeTree", "", "PBR Rock Shader"),
                          filename="PBR Rock Shader", directory=os.path.join(shader_path+"/NodeTree"))

    def _construct_ground_plane(self, ground_config):
        """ Constructs ground plane.

        :param ground_config: Config object that contains user-defined settings for ground plane.
        """
        # get scale\'size' of a plane to be created 10x10 if not defined
        plane_scale = ground_config.get_vector3d("plane_scale", [1, 1, 1])
        # get the amount of subdiv cuts, 50 (50x50=250 segments) if not defined
        subdivision_cuts = ground_config.get_int("subdivision_cuts", 50)
        # get the amount of subdiv render levels, 2 if not defined
        subdivision_render_levels = ground_config.get_int("subdivision_render_levels", 3)
        # get displacement strength, 1 if not defined
        displacement_strength = ground_config.get_float("displacement_strength", 1)
        # get name, 'RE_ground_plane' if not defined
        tile_name = ground_config.get_string("tile_name", "RE_ground_plane")
        # get AO color
        ao = ground_config.get_list("AO", [1, 1, 1, 1])

        # create new plane, set its size
        bpy.ops.mesh.primitive_plane_add()
        bpy.context.object.name = tile_name
        plane_obj = bpy.data.objects[tile_name]
        plane_obj.scale = plane_scale

        # create new material, enable use of nodes
        mat_obj = bpy.data.materials.new(name="re_ground_mat")
        mat_obj.use_nodes = True

        # set material
        plane_obj.data.materials.append(mat_obj)
        nodes = mat_obj.node_tree.nodes
        links = mat_obj.node_tree.links

        # delete Principled BSDF node
        nodes.remove(Utility.get_nodes_with_type(nodes, "BsdfPrincipled")[0])

        # create PBR Rock Shader, connect its output 'Shader' to the Material Output nodes input 'Surface'
        group_pbr = nodes.new("ShaderNodeGroup")
        group_pbr.node_tree = bpy.data.node_groups['PBR Rock Shader']
        group_pbr.inputs["AO"].default_value = ao
        output_node = Utility.get_nodes_with_type(nodes, 'OutputMaterial')[0]
        links.new(group_pbr.outputs['Shader'], output_node.inputs['Surface'])

        # create Image Texture nodes for color, roughness, reflection, and normal maps
        self._create_node(nodes, links, 'color', 'Color')
        self._create_node(nodes, links, 'roughness', 'Roughness')
        self._create_node(nodes, links, 'reflection', 'Reflection')
        self._create_node(nodes, links, 'normal', 'Normal')

        # create subsurface and displacement modifiers
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=subdivision_cuts)
        bpy.ops.object.modifier_add(type="SUBSURF")
        bpy.ops.object.modifier_add(type="DISPLACE")

        # create new texture
        texture_name = tile_name + "_texture"
        texture = bpy.data.textures.new(name=texture_name, type="IMAGE")

        # set new texture as a displacement texture, set UV texture coordinates
        plane_obj.modifiers['Displace'].texture = bpy.data.textures[texture_name]
        plane_obj.modifiers['Displace'].texture_coords = 'UV'

        bpy.ops.object.editmode_toggle()
        # scale, set render levels for subdivision, strength of displacement and set passive rigidbody state
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.context.object.modifiers["Subdivision"].render_levels = subdivision_render_levels
        bpy.context.object.modifiers["Displace"].strength = displacement_strength
        plane_obj["physics"] = False

    def _create_node(self, nodes, links, map_type, in_point):
        """ Handles creating a ShaderNodeTexImage node, setting maps and creating links.

        :param nodes: All nodes in the node tree of the material object.
        :param links: All links in the node tree of the material object.
        :param map_type: Type of image/map that will be assigned to this node.
        :param in_point: Name of an input point in PBR Rock Shader node to use.
        """
        nodes.new('ShaderNodeTexImage')
        # set output point of the node to connect
        a = nodes.get(nodes[-1].name).outputs['Color']
        nodes[-1].label = map_type
        # special case for a normal map since the link between TextureNode and PBR RS is broken with Normal Map node
        if map_type == 'normal':
            # create new node
            group_norm_map = nodes.new('ShaderNodeNormalMap')
            # magic: pre-last node, select Color output
            a_norm = nodes.get(nodes[-2].name).outputs['Color']
            # select input point
            b_norm = group_norm_map.inputs['Color']
            # connect them
            links.new(a_norm, b_norm)
            # redefine main output point to connect
            a = nodes.get(nodes[-1].name).outputs['Normal']
        # select main input point of the PBR Rock Shader
        b = nodes.get("Group").inputs[in_point]
        links.new(a, b)
