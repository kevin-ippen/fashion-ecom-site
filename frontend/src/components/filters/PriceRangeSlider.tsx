import { useState, useEffect } from 'react';

interface PriceRangeSliderProps {
  min: number;
  max: number;
  selectedMin?: number;
  selectedMax?: number;
  onRangeChange: (min: number | undefined, max: number | undefined) => void;
}

export function PriceRangeSlider({
  min,
  max,
  selectedMin,
  selectedMax,
  onRangeChange,
}: PriceRangeSliderProps) {
  // Local state for live slider updates (before apply)
  const [minValue, setMinValue] = useState(selectedMin || min);
  const [maxValue, setMaxValue] = useState(selectedMax || max);

  // Sync with external changes
  useEffect(() => {
    setMinValue(selectedMin || min);
    setMaxValue(selectedMax || max);
  }, [selectedMin, selectedMax, min, max]);

  const handleMinChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number(e.target.value);
    // Ensure min doesn't exceed max
    const newMin = Math.min(value, maxValue - 1);
    setMinValue(newMin);
  };

  const handleMaxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number(e.target.value);
    // Ensure max doesn't go below min
    const newMax = Math.max(value, minValue + 1);
    setMaxValue(newMax);
  };

  const handleApply = () => {
    // Only apply if values differ from default range
    const shouldSetMin = minValue !== min;
    const shouldSetMax = maxValue !== max;

    onRangeChange(
      shouldSetMin ? minValue : undefined,
      shouldSetMax ? maxValue : undefined
    );
  };

  const handleReset = () => {
    setMinValue(min);
    setMaxValue(max);
    onRangeChange(undefined, undefined);
  };

  // Calculate percentage positions for the filled range bar
  const minPercent = ((minValue - min) / (max - min)) * 100;
  const maxPercent = ((maxValue - min) / (max - min)) * 100;

  const hasActiveFilter = (selectedMin !== undefined && selectedMin !== min) ||
                          (selectedMax !== undefined && selectedMax !== max);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-micro text-muted-foreground font-semibold">Price Range</h3>
        {hasActiveFilter && (
          <button
            onClick={handleReset}
            className="text-micro text-muted-foreground hover:text-foreground transition-colors underline"
          >
            Reset
          </button>
        )}
      </div>

      {/* Price Range Display */}
      <div className="flex items-center justify-between text-body-sm">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">$</span>
          <input
            type="number"
            value={minValue}
            onChange={(e) => setMinValue(Number(e.target.value))}
            onBlur={handleMinChange}
            min={min}
            max={maxValue - 1}
            className="w-20 px-2 py-1 border border-border rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>
        <span className="text-muted-foreground">–</span>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">$</span>
          <input
            type="number"
            value={maxValue}
            onChange={(e) => setMaxValue(Number(e.target.value))}
            onBlur={handleMaxChange}
            min={minValue + 1}
            max={max}
            className="w-20 px-2 py-1 border border-border rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>
      </div>

      {/* Dual Range Slider */}
      <div className="relative pt-2 pb-6">
        {/* Track background */}
        <div className="absolute top-2 left-0 right-0 h-2 bg-muted rounded-full" />

        {/* Filled range */}
        <div
          className="absolute top-2 h-2 bg-primary rounded-full transition-all duration-150"
          style={{
            left: `${minPercent}%`,
            right: `${100 - maxPercent}%`,
          }}
        />

        {/* Min slider */}
        <input
          type="range"
          min={min}
          max={max}
          value={minValue}
          onChange={handleMinChange}
          className="absolute top-0 left-0 w-full h-2 appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-primary [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:hover:scale-110 [&::-webkit-slider-thumb]:transition-transform [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-primary [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:shadow-md [&::-moz-range-thumb]:hover:scale-110 [&::-moz-range-thumb]:transition-transform"
          style={{ zIndex: minValue > max - 100 ? 5 : 3 }}
        />

        {/* Max slider */}
        <input
          type="range"
          min={min}
          max={max}
          value={maxValue}
          onChange={handleMaxChange}
          className="absolute top-0 left-0 w-full h-2 appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-primary [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:hover:scale-110 [&::-webkit-slider-thumb]:transition-transform [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-primary [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:shadow-md [&::-moz-range-thumb]:hover:scale-110 [&::-moz-range-thumb]:transition-transform"
          style={{ zIndex: 4 }}
        />
      </div>

      {/* Apply Button - only show if values changed */}
      {(minValue !== (selectedMin || min) || maxValue !== (selectedMax || max)) && (
        <button
          onClick={handleApply}
          className="w-full btn btn-primary btn-sm animate-slide-down"
        >
          Apply Price Range
        </button>
      )}

      {/* Min/Max labels */}
      <div className="flex items-center justify-between text-micro text-muted-foreground">
        <span>${min}</span>
        <span>${max}</span>
      </div>
    </div>
  );
}
