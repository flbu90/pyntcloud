from pyntcloud import PyntCloud
import numpy as np
import pandas as pd

num_points = 5

points = pd.DataFrame(np.random.rand(num_points, 6))
points.columns = ["x", "y", "z", "r", "g", "b"]
cloud = PyntCloud(points)

#cloud = PyntCloud.from_file("D:/HSD/Libs/pyntcloud/examples/data/ankylosaurus_mesh.ply")

voxelgrid_id = cloud.add_structure("voxelgrid", n_x=5, n_y=5, n_z=5)
voxelgrid = cloud.structures[voxelgrid_id]
#voxels, colors = voxelgrid.get_feature_vector(mode="color")
voxelgrid.plot(d=4, mode="color")
#voxelgrid.plot(d=4, mode="binary")

print("Done")