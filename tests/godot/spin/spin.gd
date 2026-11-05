extends MeshInstance3D
# turns at a fixed rate per frame: under Movie Maker (--fixed-fps) every frame is a pure function of its number
func _process(delta):
	rotate_y(delta * 1.5)
	rotate_x(delta * 0.6)
