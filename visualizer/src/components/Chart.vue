<template>
    <div :id="id"></div>
</template>

<script>
import c3 from 'c3'
import _ from 'lodash'

function dataToGraph(data) {
    return _.reduce(data, (d, {name, x, y}) => {
        d.columns.push([name, ...y])
        d.columns.push(['x_' + name, ...x])
        d.xs[name] = 'x_' + name
        return d
    }, {columns: [], xs: {}, type: 'scatter'})
}

export default {
    props: ['data', 'name', 'xlabel', 'ylabel'],
    methods: {
        graph(data) {
            this._chart = c3.generate({
                bindto: '#' + this.id,
                data: dataToGraph(data),
                color: {
                    pattern: ['blue', 'red', 'green']
                },
                axis: {
                    x: {
                        label: this.xlabel,
                    },
                    y: {
                        label: this.ylabel,
                    }
                }
            })
        }
    },
    computed: {
        id() {
            return `chart-${this.name}`
        },
        graphData: (vm) => {
            return dataToGraph(vm.data)
        }
    },
    watch: {
        data(_data) {
            if (!_.isEmpty(_data)) {
                this.graph(_data)
            }
        }
    }
}
</script>