
import time

class Effect:
    def begin_frame(self):
        """
        This gets called once every frame. Override this.
        """
        pass

    def shader(self, color, pixel_info, index=None):
        """
        This gets called for each pixel on the strip.
        Args:
            color: Original color of the pixel.
            pixel_info: Pixel coordinate.

        Returns: New color of the pixel.

        """
        pass

    def _begin_frame(self):
        self.time = time.time()
        self.begin_frame()

    def render(self, led_strip, coordinates, time):
        self._begin_frame()

        for ii, coord in enumerate(coordinates):
            col = led_strip[ii]
            new_col = self.shader(col, coord, ii)
            if new_col is not None:
                led_strip[ii] = new_col
