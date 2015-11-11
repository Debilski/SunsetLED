
import time

class Effect:
    def begin_frame(self):
        """
        This gets called once every frame. Override this.
        """
        pass

    def shader(self, color, pixel_info):
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
            led_strip[ii] = self.shader(col, coord)
