import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type BarPlotDatum = { name: string; value: number; colour: string };

type BarPlotProps = {
    data: BarPlotDatum[];
    layout: "horizontal" | "vertical";
    height: number;
    labelWidth?: number;
    valueFormatter?: (value: number) => string;
};

/**
 * The only module that imports Recharts. Loaded lazily by the dashboard so the
 * tables and KPIs render before the charting code arrives.
 */
export default function BarPlot({ data, layout, height, labelWidth = 0, valueFormatter }: BarPlotProps) {
    const isVertical = layout === "vertical";
    return (
        <div style={{ height }} className="w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    data={data}
                    layout={layout}
                    margin={{ top: 4, right: 16, bottom: 4, left: isVertical ? 8 : 0 }}
                >
                    <CartesianGrid horizontal={!isVertical} vertical={isVertical} stroke="#e2e8f0" />
                    {isVertical ? (
                        <>
                            <XAxis type="number" fontSize={11} tickFormatter={valueFormatter} />
                            <YAxis type="category" dataKey="name" width={labelWidth} fontSize={11} interval={0} />
                        </>
                    ) : (
                        <>
                            <XAxis dataKey="name" fontSize={11} interval={0} />
                            <YAxis allowDecimals={false} fontSize={11} width={36} />
                        </>
                    )}
                    <Tooltip formatter={valueFormatter ? (value) => valueFormatter(Number(value)) : undefined} />
                    <Bar dataKey="value" isAnimationActive={false}>
                        {data.map((entry) => (
                            <Cell key={entry.name} fill={entry.colour} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
