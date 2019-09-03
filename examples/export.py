from pyntcloud import PyntCloud
import numpy as np
import pandas as pd

#num_points = 6

#points = pd.DataFrame(5*np.random.rand(num_points, 6))
#points.columns = ["x", "y", "z", "r", "g", "b"]
#points = pd.DataFrame(5*np.random.rand(num_points, 3))
#points.columns = ["x", "y", "z"]


anky = PyntCloud.from_file("./data/ankylosaurus_mesh.ply")
anky_point_cloud = anky.get_sample("mesh_random", n=1000, rgb=True, normals=True)
#print(anky_point_cloud[["x", "y", "z"]].values[:5,:])

#num_points = 100
#points = np.random.rand(num_points, 3)
points = anky_point_cloud[["x", "y", "z"]]

#print(points.values)
cloud = PyntCloud(points)

#delaunay3D_id = cloud.add_structure("convex_hull")
#delaunay3D = cloud.structures[delaunay3D_id]
#m = delaunay3D.get_mesh()
#print(m)

#cloud.mesh = m

cloud.to_file("out_file.ply")