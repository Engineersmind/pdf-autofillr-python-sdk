class BoundingBox:
    """Class to handle bounding box information with both (l, t, r, b) and (l, t, width, height) formats."""

    def __init__(self, l, t, r=None, b=None, width=None, height=None, rounding=1):
        self.rounding = rounding  # Set rounding precision
        self.l = round(l, rounding)
        self.t = round(t, rounding)

        if r is not None and b is not None:
            # Case: Given (left, top, right, bottom)
            self.r = round(r, rounding)
            self.b = round(b, rounding)
            self.width = round(r - l, rounding)
            self.height = round(b - t, rounding)
        elif width is not None and height is not None:
            # Case: Given (left, top, width, height)
            self.width = round(width, rounding)
            self.height = round(height, rounding)
            self.r = round(l + width, rounding)
            self.b = round(t + height, rounding)
        else:
            raise ValueError("BoundingBox must have either (right, bottom) or (width, height)")

    def to_dict(self):
        """Returns the bounding box as a dictionary with rounded values."""
        return {
            "left": round(self.l, self.rounding),
            "top": round(self.t, self.rounding),
            "right": round(self.r, self.rounding),
            "bottom": round(self.b, self.rounding),
            "width": round(self.width, self.rounding),
            "height": round(self.height, self.rounding)
        }

    def __repr__(self):
        return (f"BoundingBox(l={self.l}, t={self.t}, r={self.r}, b={self.b}, "
                f"w={self.width}, h={self.height}, rounding={self.rounding})")
