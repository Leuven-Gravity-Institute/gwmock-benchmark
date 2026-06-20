// Render interactive Vega-Lite charts for benchmark results. The data is emitted
// inline by `gwmock-benchmark aggregate` as a <script type="application/json"> block;
// this builds one chart per metric next to its <div class="benchmark-charts">.
;(function () {
    'use strict'

    var COLD = '#7fcdbb'
    var WARM = '#2c7fb8'
    var SCHEMA = 'https://vega.github.io/schema/vega-lite/v5.json'

    // Per-suite chart definitions: which metric fields become which chart.
    var SUITES = {
        performance: {
            xField: 'name',
            charts: [
                {
                    title: 'Throughput',
                    y: 'events / s',
                    cold: 'throughput_cold',
                    warm: 'throughput_warm',
                },
                {
                    title: 'Wall time',
                    y: 'seconds',
                    cold: 'wall_cold',
                    warm: 'wall_warm',
                },
                { title: 'One-time compile', y: 'seconds', value: 'compile' },
                { title: 'Peak memory', y: 'GB', value: 'peak_gb' },
                { title: 'Output data', y: 'GB', value: 'output_gb' },
            ],
        },
        consistency: {
            xField: 'approximant',
            charts: [
                {
                    title: 'ripple vs LAL — worst-case overlap loss (lower is better)',
                    y: 'log₁₀(1 − overlap)',
                    value: 'worst_log_loss',
                },
            ],
        },
    }

    var X_AXIS = { labelAngle: -30, title: null, labelLimit: 280 }

    function groupedSpec(rows, xField, def) {
        var values = []
        rows.forEach(function (row) {
            values.push({
                x: row[xField],
                phase: 'cold',
                value: row[def.cold],
                device: row.device,
                label: row.label,
            })
            values.push({
                x: row[xField],
                phase: 'warm',
                value: row[def.warm],
                device: row.device,
                label: row.label,
            })
        })
        return {
            $schema: SCHEMA,
            width: 'container',
            height: 320,
            title: def.title + ' — cold vs warm',
            data: { values: values },
            params: [
                {
                    name: 'phaseSel',
                    select: { type: 'point', fields: ['phase'] },
                    bind: 'legend',
                },
            ],
            mark: { type: 'bar', tooltip: true },
            encoding: {
                x: { field: 'x', type: 'nominal', sort: null, axis: X_AXIS },
                xOffset: { field: 'phase' },
                y: { field: 'value', type: 'quantitative', title: def.y },
                color: {
                    field: 'phase',
                    title: null,
                    scale: { domain: ['cold', 'warm'], range: [COLD, WARM] },
                },
                opacity: {
                    condition: { param: 'phaseSel', value: 1 },
                    value: 0.25,
                },
                tooltip: [
                    { field: 'label', title: 'cell' },
                    { field: 'device' },
                    { field: 'phase' },
                    {
                        field: 'value',
                        type: 'quantitative',
                        format: '.4g',
                        title: def.y,
                    },
                ],
            },
        }
    }

    function singleSpec(rows, xField, def) {
        var values = rows.map(function (row) {
            return {
                x: row[xField],
                value: row[def.value],
                device: row.device,
                label: row.label,
            }
        })
        return {
            $schema: SCHEMA,
            width: 'container',
            height: 320,
            title: def.title,
            data: { values: values },
            mark: { type: 'bar', tooltip: true, color: WARM },
            encoding: {
                x: { field: 'x', type: 'nominal', sort: null, axis: X_AXIS },
                y: { field: 'value', type: 'quantitative', title: def.y },
                tooltip: [
                    { field: 'label', title: 'cell' },
                    { field: 'device' },
                    {
                        field: 'value',
                        type: 'quantitative',
                        format: '.5g',
                        title: def.y,
                    },
                ],
            },
        }
    }

    function render(container) {
        if (container.dataset.rendered === 'true') return
        var group = container.getAttribute('data-group')
        var suite = container.getAttribute('data-suite')
        var config = SUITES[suite]
        var script = document.querySelector(
            'script.benchmark-chart-data[data-group="' + group + '"]'
        )
        if (!config || !script || typeof window.vegaEmbed === 'undefined')
            return
        container.dataset.rendered = 'true'

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
            var spec = def.value
                ? singleSpec(rows, config.xField, def)
                : groupedSpec(rows, config.xField, def)
            window.vegaEmbed(div, spec, {
                actions: {
                    export: true,
                    source: false,
                    compiled: false,
                    editor: false,
                },
                renderer: 'svg',
            })
        })
    }

    function init() {
        document.querySelectorAll('.benchmark-charts').forEach(render)
    }

    if (typeof window.document$ !== 'undefined' && window.document$.subscribe) {
        window.document$.subscribe(init)
    } else {
        document.addEventListener('DOMContentLoaded', init)
    }
})()
