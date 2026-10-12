# Donkey Kong 64

Tools for replacing D64 models. Supports importing of actors, props and stages, exporting of actors and props

The blender to DK64 scale is similar to how it works in SM64 where you can manipulate their import and export scale. This implementation is strictly for reducing the vertex snapping on high poly models.

The bones are also similar in structure to what you would see in SM64. Animated bones hold the mesh, scale bones are at the root of the heiarchy and control the scaling of the mesh and it goes in hand with the blender to DK64 scale, finally the switch bone is for optional meshes which switch out in game such as weapons.
