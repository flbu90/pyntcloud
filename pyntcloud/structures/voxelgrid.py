import numpy as np

try:
    import matplotlib.pyplot as plt
    is_matplotlib_avaliable = True
except ImportError:
    is_matplotlib_avaliable = False

from scipy.spatial import cKDTree

from .base import Structure
from ..plot import plot_voxelgrid
from ..utils.array import cartesian

try:
    from ..utils.numba import groupby_max, groupby_count, groupby_sum
    is_numba_avaliable = True
except ImportError:
    is_numba_avaliable = False


class VoxelGrid(Structure):

    def __init__(self, *, points, rgb, normals, curvatures, n_x=1, n_y=1, n_z=1, size_x=None, size_y=None, size_z=None, regular_bounding_box=True):
        """Grid of voxels with support for different build methods.

        Parameters
        ----------
        points: (N, 3) numpy.array
        n_x, n_y, n_z :  int, optional
            Default: 1
            The number of segments in which each axis will be divided.
            Ignored if corresponding size_x, size_y or size_z is not None.
        size_x, size_y, size_z : float, optional
            Default: None
            The desired voxel size along each axis.
            If not None, the corresponding n_x, n_y or n_z will be ignored.
        regular_bounding_box : bool, optional
            Default: True
            If True, the bounding box of the point cloud will be adjusted
            in order to have all the dimensions of equal length.
        """
        super().__init__(points=points, rgb=rgb, normals=normals, curvatures=curvatures)
        self.x_y_z = [n_x, n_y, n_z]
        self.sizes = [size_x, size_y, size_z]
        self.regular_bounding_box = regular_bounding_box

    def compute(self):
        """ABC API."""
        xyzmin = self._points.min(0)
        xyzmax = self._points.max(0)

        if self.regular_bounding_box:
            #range = xyzmax - xyzmin
            #: adjust to obtain a minimum bounding box with all sides of equal length
            margin = max(xyzmax - xyzmin) - (xyzmax - xyzmin)
            xyzmin = xyzmin - margin / 2
            xyzmax = xyzmax + margin / 2

        for n, size in enumerate(self.sizes):
            if size is None:
                continue
            margin = (((self._points.ptp(0)[n] // size) + 1) * size) - self._points.ptp(0)[n]
            xyzmin[n] -= margin / 2
            xyzmax[n] += margin / 2
            self.x_y_z[n] = ((xyzmax[n] - xyzmin[n]) / size).astype(int)

        self.xyzmin = xyzmin
        self.xyzmax = xyzmax

        segments = []
        shape = []
        for i in range(3):
            # note the +1 in num
            # for example n_x = 30 -> divide x_min to x_max into 30 equally sized samples and return the step size
            s, step = np.linspace(xyzmin[i], xyzmax[i], num=(self.x_y_z[i] + 1), retstep=True)
            # list of arrays of each axis
            segments.append(s)
            # size of spacing of each axis
            shape.append(step)

        self.segments = segments
        self.shape = shape

        self.n_voxels = self.x_y_z[0] * self.x_y_z[1] * self.x_y_z[2]

        # store the parameters of this voxelgrid
        self.id = "V({},{},{})".format(self.x_y_z, self.sizes, self.regular_bounding_box)

        # find where each point lies in corresponding segmented axis
        # -1 so index are 0-based; clip for edge cases
        self.voxel_x = np.clip(np.searchsorted(self.segments[0], self._points[:, 0]) - 1, 0, self.x_y_z[0])
        self.voxel_y = np.clip(np.searchsorted(self.segments[1], self._points[:, 1]) - 1, 0, self.x_y_z[1])
        self.voxel_z = np.clip(np.searchsorted(self.segments[2], self._points[:, 2]) - 1, 0,  self.x_y_z[2])
        self.voxel_n = np.ravel_multi_index([self.voxel_x, self.voxel_y, self.voxel_z], self.x_y_z)

        # compute center of each voxel
        midsegments = [(self.segments[i][1:] + self.segments[i][:-1]) / 2 for i in range(3)]
        self.voxel_centers = cartesian(midsegments).astype(np.float32)

    def query(self, points):
        """ABC API. Query structure.

        TODO Make query_voxelgrid an independent function, and add a light
        save mode where only segments and x_y_z are saved.
        """
        voxel_x = np.clip(np.searchsorted(
            self.segments[0], points[:, 0]) - 1, 0, self.x_y_z[0])
        voxel_y = np.clip(np.searchsorted(
            self.segments[1], points[:, 1]) - 1, 0, self.x_y_z[1])
        voxel_z = np.clip(np.searchsorted(
            self.segments[2], points[:, 2]) - 1, 0, self.x_y_z[2])
        voxel_n = np.ravel_multi_index([voxel_x, voxel_y, voxel_z], self.x_y_z)

        return voxel_n, voxel_x, voxel_y, voxel_z

    def get_feature_vector(self, mode="binary"):
        """Return a vector of size self.n_voxels. See mode options below.

        Parameters
        ----------
        mode: str in available modes. See Notes
            Default "binary"

        Returns
        -------
        feature_vector: [n_x, n_y, n_z] ndarray
            See Notes.

        Notes
        -----
        Available modes are:

        binary
            0 for empty voxels, 1 for occupied.

        density
            number of points inside voxel / total number of points.

        TDF
            Truncated Distance Function. Value between 0 and 1 indicating the distance
            between the voxel's center and the closest point. 1 on the surface,
            0 on voxels further than 2 * voxel side.

        x_max, y_max, z_max
            Maximum coordinate value of points inside each voxel.

        x_mean, y_mean, z_mean
            Mean coordinate value of points inside each voxel.
        """
        vector = np.zeros(self.n_voxels)

        if mode == "binary":
            vector[np.unique(self.voxel_n)] = 1
        
        elif mode == "color":
            # each voxel index has a rgba array
            color = np.zeros((self.n_voxels,4))
            
            voxel_idxs = []
            for i in range(len(self.voxel_n)):
                # check if we already have seen an index
                voxel_idx = self.voxel_n[i]
                if(voxel_idx in voxel_idxs):
                    continue
                # new voxel_idx -- mark it as seen
                voxel_idxs.append(voxel_idx)
                # get the list indexes of the voxel_idx
                voxel_list_idxs = np.where(self.voxel_n == voxel_idx)
                # compute the mean color of these voxels
                mean_color = np.mean(self._rgb[voxel_list_idxs], axis=0)
                # append an alpha value of 1
                color[voxel_idx] = np.append(mean_color, [1])
                
            # we need a shape of (n_X, n_Y, n_Z, 4), 4 for rgba
            color = color.reshape(self.x_y_z + [5])
            vector[np.unique(self.voxel_n)] = 1
            vector = vector.reshape(self.x_y_z)
            return vector, color
        elif mode == "custom":
            features = np.zeros((self.n_voxels,5))
            voxel_idxs = []
            for i in range(len(self.voxel_n)):
                voxel_idx = self.voxel_n[i]
                if(voxel_idx in voxel_idxs):
                    continue
                voxel_idxs.append(voxel_idx)
                voxel_list_idxs = np.where(self.voxel_n == voxel_idx)
                mean_normal = np.mean(self._normals[voxel_list_idxs], axis=0)
                mean_curvature = np.mean(self._curvatures[voxel_list_idxs])
                occ = np.array([1.0])
                feature = np.concatenate((occ, mean_normal, [mean_curvature]))
                #print(feature.shape)
                features[voxel_idx] = feature
                
            features = features.reshape(self.x_y_z + [5])
            vector[np.unique(self.voxel_n)] = 1
            vector = vector.reshape(self.x_y_z)
            return vector, features
            
        elif mode == "density":
            count = np.bincount(self.voxel_n)
            vector[:len(count)] = count
            vector /= len(self.voxel_n)

        elif mode == "TDF":
            # truncation = np.linalg.norm(self.shape)
            kdt = cKDTree(self._points)
            vector, i = kdt.query(self.voxel_centers, n_jobs=-1)

        elif mode.endswith("_max"):
            if not is_numba_avaliable:
                raise ImportError("numba is required to compute {}".format(mode))
            axis = {"x_max": 0, "y_max": 1, "z_max": 2}
            vector = groupby_max(self._points, self.voxel_n, axis[mode], vector)

        elif mode.endswith("_mean"):
            if not is_numba_avaliable:
                raise ImportError("numba is required to compute {}".format(mode))
            axis = {"x_mean": 0, "y_mean": 1, "z_mean": 2}
            voxel_sum = groupby_sum(self._points, self.voxel_n, axis[mode], np.zeros(self.n_voxels))
            voxel_count = groupby_count(self._points, self.voxel_n, np.zeros(self.n_voxels))
            vector = np.nan_to_num(voxel_sum / voxel_count)

        else:
            raise NotImplementedError("{} is not a supported feature vector mode".format(mode))

        return vector.reshape(self.x_y_z)

    def get_voxel_neighbors(self, voxel):
        """Get valid, non-empty 26 neighbors of voxel.

        Parameters
        ----------
        voxel: int in self.set_voxel_n

        Returns
        -------
        neighbors: list of int
            Indices of the valid, non-empty 26 neighborhood around voxel.
        """

        x, y, z = np.unravel_index(voxel, self.x_y_z)

        valid_x = []
        valid_y = []
        valid_z = []
        if x - 1 >= 0:
            valid_x.append(x - 1)
        if y - 1 >= 0:
            valid_y.append(y - 1)
        if z - 1 >= 0:
            valid_z.append(z - 1)

        valid_x.append(x)
        valid_y.append(y)
        valid_z.append(z)

        if x + 1 < self.x_y_z[0]:
            valid_x.append(x + 1)
        if y + 1 < self.x_y_z[1]:
            valid_y.append(y + 1)
        if z + 1 < self.x_y_z[2]:
            valid_z.append(z + 1)

        valid_neighbor_indices = cartesian((valid_x, valid_y, valid_z))

        ravel_indices = np.ravel_multi_index((valid_neighbor_indices[:, 0],
                                              valid_neighbor_indices[:, 1],
                                              valid_neighbor_indices[:, 2]), self.x_y_z)

        return [x for x in ravel_indices if x in np.unique(self.voxel_n)]

    def plot(self,
             d=2,
             mode="binary",
             cmap="Oranges",
             axis=False,
             output_name=None,
             width=800,
             height=500,
             edge_color='red'):

        if d == 2:
            feature_vector = self.get_feature_vector(mode)
            if not is_matplotlib_avaliable:
                raise ImportError("matplotlib is required for 2d plotting")

            fig, axes = plt.subplots(
                int(np.ceil(self.x_y_z[2] / 4)), 4, figsize=(20, 20))
            plt.tight_layout()
            for i, ax in enumerate(axes.flat):
                if i >= len(feature_vector):
                    break
                ax.imshow(feature_vector[:, :, i],
                          cmap=cmap, interpolation="nearest")
                ax.set_title("Level " + str(i))

        elif d == 3:
            return plot_voxelgrid(self,
                                  mode=mode,
                                  cmap=cmap,
                                  axis=axis,
                                  output_name=output_name,
                                  width=width,
                                  height=height)
        elif d == 4:
            fig = plt.figure()
            ax = fig.gca(projection='3d')
            if mode == "binary":
                voxels = self.get_feature_vector(mode)
                ax.voxels(voxels, edgecolor=edge_color)
            elif mode == "color":
                voxels, colors = self.get_feature_vector(mode=mode)
                ax.voxels(voxels, edgecolor=edge_color, facecolors=colors)
            else:
                raise NotImplementedError("Only color and binary are implemented.")
            plt.show()
