from pyntcloud import PyntCloud
import numpy as np
import pandas as pd

num_points = 100

points = pd.DataFrame(np.random.rand(num_points, 6))
points.columns = ["x", "y", "z", "r", "g", "b"]
#print(points.values)
cloud = PyntCloud(points)

#cloud = PyntCloud.from_file("D:/HSD/Libs/pyntcloud/examples/data/ankylosaurus_mesh.ply")

voxelgrid_id = cloud.add_structure("voxelgrid", n_x=5, n_y=5, n_z=5)
voxelgrid = cloud.structures[voxelgrid_id]
#voxels, colors = voxelgrid.get_feature_vector(mode="color")
voxelgrid.plot(d=4, mode="color", edge_color="none")
#voxelgrid.plot(d=4, mode="binary")

voxels, colors = voxelgrid.get_feature_vector(mode="color")

# removing unneccesary alpha value
mcolor = colors[:,:,:,:3]
#print(mcolor.shape)
#print(mcolor)

print("Done")