def fixed_units_axis(axis):
    """Keep public mm/mT/mV labels and ticks in the same units across updates."""
    if hasattr(axis, "setSIPrefixEnableRanges"):
        axis.setSIPrefixEnableRanges(())
    axis.enableAutoSIPrefix(False)
    axis.autoSIPrefixScale = 1.0
    axis.picture = None
    axis.update()
