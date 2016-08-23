from __future__ import division
from shapely.geometry import Polygon, Point
import pkg_resources


class SearchArea(object):
    """An object that detects when the plane is inside the search area."""
    def __init__(self):
        
        data_path = pkg_resources.resource_filename('AUVSIground', 'resources/search_area.txt')
        
        coords = []
        with open(data_path, 'rb') as f:
            for line in f:
                coords.append([float(l) for l in line.strip().split()[::-1]])
                
        self._pol = Polygon(coords)
        
    @property
    def pol(self):
        
        return self._pol
    
    def test_collision(self, lon, lat):
        """Check if a lon, lat coordinate is inside the search area."""
        
        distance = Point(lon, lat).distance(self.pol)
        return distance == 0
        
    
if __name__ == '__main__':
    
    import matplotlib.pyplot as plt
    
    def plot_coords(ax, ob):
        x, y = ob.xy
        ax.plot(x, y, 'o', color='#999999', zorder=1)
    
    def plot_line(ax, ob):
        x, y = ob.xy
        ax.plot(x, y, linewidth=3, solid_capstyle='round', zorder=2)

    sa = SearchArea()
    
    fig = plt.figure(0)
    ax = fig.add_subplot(111)
    plot_line(ax, sa.pol.exterior)
    plt.show()
    
    print sa.test_collision(lon=-76.43, lat=38.149) > 0
    print sa.test_collision(lon=-76.428, lat=38.1485) > 0