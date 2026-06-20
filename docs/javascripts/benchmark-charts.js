// Render interactive Vega-Lite charts for benchmark results. The data is emitted
// inline by `gwmock-benchmark aggregate` as a <script type="application/json"> block;
// this builds one chart per metric next to its <div class="benchmark-charts">.
//
// The x-axis is the waveform model (approximant), not the hardware: each
// backend/method/hardware cell is a coloured scatter point, so models are compared
// side by side and the hardware comparison lives in the colour legend. Models are
// sorted with the best result on the left (per chart: highest throughput, lowest
// wall/memory/loss).
;(function () {
    'use strict'

    var COLD = '#7fcdbb'
    var WARM = '#2c7fb8'
    var SCHEMA = 'https://vega.github.io/schema/vega-lite/v5.json'

    // Per-suite chart definitions: which metric fields become which chart.
    // higherBetter drives the model sort order (best on the left).
    var SUITES = {
        performance: {
            xField: 'approximant',
            charts: [
                {
                    title: 'Throughput',
                    y: 'events / s',
                    cold: 'throughput_cold',
                    warm: 'throughput_warm',
                    higherBetter: true,
                },
                {
                    title: 'Wall time',
                    y: 'seconds',
                    cold: 'wall_cold',
                    warm: 'wall_warm',
                    higherBetter: false,
                },
                {
                    title: 'One-time compile',
                    y: 'seconds',
                    value: 'compile',
                    higherBetter: false,
                },
                {
                    title: 'Peak memory',
                    y: 'GB',
                    value: 'peak_gb',
                    higherBetter: false,
                },
                {
                    title: 'Output data',
                    y: 'GB',
                    value: 'output_gb',
                    higherBetter: false,
                },
            ],
        },
        consistency: {
            xField: 'approximant',
            charts: [
                {
                    title: 'ripple vs LAL — log₁₀ overlap loss',
                    y: 'log₁₀(1 − overlap)',
                    pair: [
                        { key: 'worst_log_loss', name: 'worst' },
                        { key: 'median_log_loss', name: 'median' },
                    ],
                },
            ],
        },
    }

    var X_AXIS = { labelAngle: -30, title: 'waveform model', labelLimit: 280 }

    // Sort the model categories so the best result sits on the left. Aggregating by
    // max (higher-is-better) or min (lower-is-better) picks the headline (warm) value.
    function modelSort(def) {
        return {
            op: def.higherBetter ? 'max' : 'min',
            field: 'value',
            order: def.higherBetter ? 'descending' : 'ascending',
        }
    }

    // Click a cell in the legend to isolate it; everyone else fades.
    function cellHighlight() {
        return {
            name: 'cellSel',
            select: { type: 'point', fields: ['cell'] },
            bind: 'legend',
        }
    }

    function cellTooltip(extra) {
        return [
            { field: 'cell', title: 'cell' },
            { field: 'approximant', title: 'model' },
            { field: 'device' },
            { field: 'version', title: 'gwmock-signal' },
        ].concat(extra || [])
    }

    // Performance throughput/wall: one point per cell, cold and warm by shape.
    function groupedSpec(rows, xField, def) {
        var values = []
        rows.forEach(function (row) {
            ;['cold', 'warm'].forEach(function (phase) {
                values.push({
                    x: row[xField],
                    cell: row.cell,
                    approximant: row.approximant,
                    device: row.device,
                    version: row.version,
                    phase: phase,
                    value: row[def[phase]],
                })
            })
        })
        return {
            $schema: SCHEMA,
            width: 'container',
            height: 340,
            title: def.title + ' — cold vs warm (best on the left)',
            data: { values: values },
            params: [cellHighlight()],
            mark: { type: 'point', filled: true, size: 110, tooltip: true },
            encoding: {
                x: {
                    field: 'x',
                    type: 'nominal',
                    sort: modelSort(def),
                    axis: X_AXIS,
                },
                y: { field: 'value', type: 'quantitative', title: def.y },
                color: { field: 'cell', type: 'nominal', title: null },
                shape: {
                    field: 'phase',
                    title: null,
                    scale: {
                        domain: ['cold', 'warm'],
                        range: ['triangle-up', 'circle'],
                    },
                },
                opacity: {
                    condition: { param: 'cellSel', value: 1 },
                    value: 0.2,
                },
                tooltip: cellTooltip([
                    { field: 'phase' },
                    {
                        field: 'value',
                        type: 'quantitative',
                        format: '.4g',
                        title: def.y,
                    },
                ]),
            },
        }
    }

    // Performance compile/memory/output: one point per cell (single value).
    function singleSpec(rows, xField, def) {
        var values = rows.map(function (row) {
            return {
                x: row[xField],
                cell: row.cell,
                approximant: row.approximant,
                device: row.device,
                version: row.version,
                value: row[def.value],
            }
        })
        return {
            $schema: SCHEMA,
            width: 'container',
            height: 340,
            title: def.title + ' (best on the left)',
            data: { values: values },
            params: [cellHighlight()],
            mark: { type: 'point', filled: true, size: 120, tooltip: true },
            encoding: {
                x: {
                    field: 'x',
                    type: 'nominal',
                    sort: modelSort(def),
                    axis: X_AXIS,
                },
                y: { field: 'value', type: 'quantitative', title: def.y },
                color: { field: 'cell', type: 'nominal', title: null },
                opacity: {
                    condition: { param: 'cellSel', value: 1 },
                    value: 0.2,
                },
                tooltip: cellTooltip([
                    {
                        field: 'value',
                        type: 'quantitative',
                        format: '.5g',
                        title: def.y,
                    },
                ]),
            },
        }
    }

    // Consistency: worst- and median-case log overlap loss per model. Lower (more
    // negative) is better, so models sort by their worst case ascending — best on left.
    function pairSpec(rows, xField, def) {
        var values = []
        rows.forEach(function (row) {
            def.pair.forEach(function (metric) {
                values.push({
                    x: row[xField],
                    approximant: row.approximant,
                    device: row.device,
                    version: row.version,
                    kind: metric.name,
                    value: row[metric.key],
                })
            })
        })
        return {
            $schema: SCHEMA,
            width: 'container',
            height: 340,
            title: def.title + ' — lower is better (best on the left)',
            data: { values: values },
            mark: { type: 'point', filled: true, size: 140, tooltip: true },
            encoding: {
                x: {
                    field: 'x',
                    type: 'nominal',
                    sort: { op: 'max', field: 'value', order: 'ascending' },
                    axis: X_AXIS,
                },
                y: { field: 'value', type: 'quantitative', title: def.y },
                color: {
                    field: 'kind',
                    title: null,
                    scale: { domain: ['worst', 'median'], range: [WARM, COLD] },
                },
                shape: {
                    field: 'kind',
                    title: null,
                    scale: {
                        domain: ['worst', 'median'],
                        range: ['circle', 'diamond'],
                    },
                },
                tooltip: [
                    { field: 'approximant', title: 'model' },
                    { field: 'version', title: 'gwmock-signal' },
                    { field: 'device' },
                    { field: 'kind' },
                    {
                        field: 'value',
                        type: 'quantitative',
                        format: '.2f',
                        title: def.y,
                    },
                ],
            },
        }
    }

    function specFor(rows, xField, def) {
        if (def.pair) return pairSpec(rows, xField, def)
        if (def.value) return singleSpec(rows, xField, def)
        return groupedSpec(rows, xField, def)
    }

    // Charts drawn on the current page: re-embedded (not just recoloured) when the
    // light/dark palette toggles, so axes, text, and legends follow the theme.
    var drawn = []

    // Material/zensical sets data-md-color-scheme="slate" on <body> for dark mode.
    // Override only the chrome (text, axes, legend, grid); data colours are shared.
    function themeConfig() {
        var dark =
            document.body.getAttribute('data-md-color-scheme') === 'slate'
        if (!dark) return { background: 'transparent' }
        var fg = '#e3e3e3'
        var muted = '#9aa0a6'
        var grid = '#3a3f44'
        return {
            background: 'transparent',
            title: { color: fg, subtitleColor: muted },
            axis: {
                labelColor: muted,
                titleColor: fg,
                gridColor: grid,
                domainColor: grid,
                tickColor: grid,
            },
            legend: { labelColor: muted, titleColor: fg },
            view: { stroke: 'transparent' },
        }
    }

    function embed(chart) {
        // Tear down a prior render so a theme toggle replaces rather than stacks.
        if (chart.view && chart.view.finalize) chart.view.finalize()
        chart.div.innerHTML = ''
        window
            .vegaEmbed(chart.div, chart.spec, {
                actions: {
                    export: true,
                    source: false,
                    compiled: false,
                    editor: false,
                },
                renderer: 'svg',
                config: themeConfig(),
            })
            .then(function (result) {
                chart.view = result.view
            })
            .catch(function () {})
    }

    function drawAll() {
        if (typeof window.vegaEmbed === 'undefined') return
        drawn.forEach(embed)
    }

    function build(container) {
        var group = container.getAttribute('data-group')
        var suite = container.getAttribute('data-suite')
        var config = SUITES[suite]
        var script = document.querySelector(
            'script.benchmark-chart-data[data-group="' + group + '"]'
        )
        if (!config || !script) return

        var rows
        try {
            rows = JSON.parse(script.textContent)
        } catch (error) {
            return
        }

        config.charts.forEach(function (def) {
            var div = document.createElement('div')
            div.className = 'benchmark-chart'
            container.appendChild(div)
            drawn.push({ div: div, spec: specFor(rows, config.xField, def) })
        })
    }

    // Redraw every chart whenever the body's colour scheme attribute changes.
    var watching = false
    function watchTheme() {
        if (watching || typeof MutationObserver === 'undefined') return
        watching = true
        new MutationObserver(function (mutations) {
            if (
                mutations.some(
                    (m) => m.attributeName === 'data-md-color-scheme'
                )
            )
                drawAll()
        }).observe(document.body, {
            attributes: true,
            attributeFilter: ['data-md-color-scheme'],
        })
    }

    function init() {
        // Instant navigation swaps the DOM, so rebuild from the current page's nodes.
        drawn = []
        document.querySelectorAll('.benchmark-charts').forEach(build)
        drawAll()
        watchTheme()
    }

    if (typeof window.document$ !== 'undefined' && window.document$.subscribe) {
        window.document$.subscribe(init)
    } else {
        document.addEventListener('DOMContentLoaded', init)
    }
})()
