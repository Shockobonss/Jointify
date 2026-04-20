import bpy

bl_info = {
    "name": "Jointify",
    "author": "Mateusz Gmachowski",
    "version": (1, 0, 7),
    "blender": (5, 0, 1),
    "location": "View3D > N-Panel > Tool",
    "description": "UE-like visualization for skeletons",
    "category": "Object",
}

# --- UPDATE CALLBACKS ---

def update_armature_view(self, context):
    """Updates armature display settings with optimized viewport refresh"""
    obj = context.active_object
    # Bezpieczne sprawdzenie czy obiekt istnieje i jest armaturą
    if not obj or obj.type != 'ARMATURE':
        return
        
    props = context.scene.jointify_settings
    arm = obj.data
    
    # Podstawowe ustawienia wyświetlania
    arm.show_axes = props.show_axes
    arm.show_names = props.show_names
    
    # Blender 4.x/5.x show_bone_colors
    if hasattr(arm, "show_bone_colors"):
        arm.show_bone_colors = props.show_bone_colors
    elif hasattr(arm, "show_bone_custom_colors"):
        arm.show_bone_custom_colors = props.show_bone_colors
    
    # Odświeżanie nakładek widoku
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        if hasattr(space.overlay, "show_bone_color"):
                            space.overlay.show_bone_color = props.show_bone_colors
                area.tag_redraw()
            
    obj.display_type = 'WIRE' if props.display_as_wire else 'TEXTURED'

# --- 1. PROPERTIES ---
class JointifySettings(bpy.types.PropertyGroup):
    custom_shape_object: bpy.props.PointerProperty(
        name="Custom Shape",
        type=bpy.types.Object,
        description="Select a custom object to use as bone shape"
    )
    
    wire_width: bpy.props.FloatProperty(
        name="Wire Width",
        default=1.0, min=0.1, max=10.0
    )
    bone_scale: bpy.props.FloatProperty(
        name="Scale",
        default=1.0, min=0.001, max=1000.0 # Zwiększono limit z 100.0 na 1000.0
    )
    bone_color: bpy.props.EnumProperty(
        name="Bone Color",
        items=[(f'THEME{i:02d}', f'Theme {i:02d}', "", f'RGN_INDEX_{i:02d}', i) for i in range(1, 21)],
        default='THEME13'
    )
    
    show_axes: bpy.props.BoolProperty(name="Axes", default=False, update=update_armature_view)
    show_names: bpy.props.BoolProperty(name="Names", default=False, update=update_armature_view)
    show_bone_colors: bpy.props.BoolProperty(name="Colors", default=True, update=update_armature_view)
    display_as_wire: bpy.props.BoolProperty(name="Wire", default=False, update=update_armature_view)

# --- 2. OPERATORS ---
class OBJECT_OT_EmptyInitialize(bpy.types.Operator):
    bl_idname = "jointify.empty_initialize"
    bl_label = "Initialize Joint Shape"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        wgt_name = "WGT_Joint_Sphere"
        props = context.scene.jointify_settings
        empty_obj = bpy.data.objects.get(wgt_name)
        
        if not empty_obj:
            col_name = "Jointify_Resources"
            res_col = bpy.data.collections.get(col_name) or bpy.data.collections.new(col_name)
            if col_name not in context.scene.collection.children:
                context.scene.collection.children.link(res_col)
            res_col.hide_viewport = True
                
            bpy.ops.object.empty_add(type='SPHERE', radius=0.01)
            empty_obj = context.active_object
            empty_obj.name = wgt_name
            
            for col in empty_obj.users_collection:
                col.objects.unlink(empty_obj)
            res_col.objects.link(empty_obj)
            
        props.custom_shape_object = empty_obj
        return {'FINISHED'}

class POSE_OT_JointifyBones(bpy.types.Operator):
    bl_idname = "jointify.bones_update"
    bl_label = "Update Selected Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'ARMATURE' and context.mode == 'POSE'

    def execute(self, context):
        props = context.scene.jointify_settings
        obj = context.active_object
        arm = obj.data

        shape_to_use = props.custom_shape_object or bpy.data.objects.get("WGT_Joint_Sphere")
        if not shape_to_use:
            self.report({'ERROR'}, "Initialize widget first!")
            return {'CANCELLED'}

        if hasattr(arm, "show_bone_colors"):
            arm.show_bone_colors = props.show_bone_colors
        arm.relation_line_position = 'HEAD'
        
        selected_bones = context.selected_pose_bones
        if not selected_bones:
            return {'FINISHED'}

        s = props.bone_scale
        scale_vec = (s, s, s)
        b_color = props.bone_color
        w_width = props.wire_width

        for pb in selected_bones:
            pb.color.palette = b_color
            pb.custom_shape = shape_to_use
            pb.use_custom_shape_bone_size = False
            pb.custom_shape_scale_xyz = scale_vec
            
            if hasattr(pb, "custom_shape_wire_width"):
                pb.custom_shape_wire_width = w_width
            elif hasattr(pb, "custom_shape_thickness"):
                pb.custom_shape_thickness = w_width

        update_armature_view(self, context)
        return {'FINISHED'}

# --- 3. UI PANEL ---
class VIEW3D_PT_my_tools_panel(bpy.types.Panel):
    bl_label = "Jointify"
    bl_idname = "VIEW3D_PT_my_tools_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.jointify_settings
        obj = context.active_object
        
        col = layout.column(align=True)
        col.operator("jointify.empty_initialize", icon='MESH_ICOSPHERE')
        col.prop(props, "custom_shape_object", text="", icon='OUTLINER_OB_MESH')
        
        layout.separator()
        
        col = layout.column(align=True)
        col.label(text="Shape Configuration", icon='SETTINGS')
        col.prop(props, "bone_color", text="Color")
        col.prop(props, "bone_scale", text="Scale")
        col.prop(props, "wire_width", text="Thickness")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.label(text="Viewport Display", icon='HIDE_OFF')
        row = col.row(align=True)
        row.prop(props, "show_axes", toggle=True, icon='ORIENTATION_LOCAL')
        row.prop(props, "show_names", toggle=True, icon='SORTALPHA')
        row = col.row(align=True)
        row.prop(props, "show_bone_colors", toggle=True, icon='COLOR')
        row.prop(props, "display_as_wire", toggle=True, icon='SHADING_WIRE')
        
        layout.separator()
        
        col = layout.column()
        # POPRAWKA BŁĘDU: Wymuszenie zwrócenia True/False (bool)
        is_armature = bool(obj and obj.type == 'ARMATURE')
        col.enabled = is_armature
        col.scale_y = 1.2
        col.operator("jointify.bones_update", icon='CHECKMARK', text="UPDATE SELECTED BONES")

# --- 4. REGISTRATION ---
classes = (JointifySettings, OBJECT_OT_EmptyInitialize, POSE_OT_JointifyBones, VIEW3D_PT_my_tools_panel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.jointify_settings = bpy.props.PointerProperty(type=JointifySettings)
        
def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.jointify_settings

if __name__ == "__main__":
    register()