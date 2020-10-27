<template>
  <v-app>
    <v-app-bar
      app
      color="primary"
      dark
    >
      <div class="d-flex align-center">
        <v-app-name>Diskplorer visualizer</v-app-name>
      </div>

      <v-spacer></v-spacer>
      <v-file-input @change="processFile" label="Results file" accept="text/csv,text/json,application/json,.csv,.json"></v-file-input>
    </v-app-bar>

    <v-main>

      <Chart name="LatencyConcurrency" xlabel="Concurrency" ylabel="Latency" :data="latencyConcurrency"></Chart>
      <Chart name="IOPSConcurrency" xlabel="Concurrency" ylabel="IOPS" :data="iopsConcurrency"></Chart>
      <Chart name="LatencyIOPS" xlabel="iops" ylabel="Latency" :data="latencyIOPS"></Chart>
    </v-main>
  </v-app>
</template>

<script>

function parseCsvToColumns(csvText) {
  let lines = _.split(csvText, '\n')
  let fields = _.head(lines).split(',')
  let parsed = {}
  
  fields.forEach(field => {
    parsed[field] = []
  })

  _.slice(lines, 1).forEach(line => {
    let row = _.split(line, ',')
    fields.forEach((field, i) => {
      parsed[field].push(row[i])
    })
  })

return parsed
}


import Chart from './components/Chart.vue'
import _ from 'lodash' 

export default {
  name: 'App',

  components: {
    Chart,
  },

  methods: {
    graph(results) {
      this.latencyIOPS = [{name: 'latency/iops', x: results.iops, y: results.latencyMean}]
      this.latencyConcurrency = [
        {name: 'latency/concurrency', x: results.concurrency, y: results.latencyMean}, 
        {name: 'latency(p95)', x: results.concurrency, y: results.latencyP95},
        {name: 'latency(p05)', x: results.concurrency, y: results.latencyP05}
      ]
      this.iopsConcurrency = [{name: 'iops/concurrency', x: results.concurrency, y: results.iops}]
    },
    processCSV(csv) {
      let results = parseCsvToColumns(csv)
      let iops = results.iops.map(x => Number.parseFloat(x))
      let latencyMean = results.lat_avg.map(x => Number.parseFloat(x))
      let latencyP05 = results.lat_05.map(x => Number.parseFloat(x))
      let latencyP95 = results.lat_95.map(x => Number.parseFloat(x))
      let concurrency = results.concurrency.map(x => Number.parseInt(x))
      this.graph({concurrency, latencyP05, latencyP95, latencyMean, iops})
    },
    processJSON(jsonText) {
      const data = JSON.parse(jsonText)
      let results = _.reduce(data['jobs'], (h, {jobname, read}) => {
        h.concurrency.push(Number.parseInt(jobname))
        h.latencyMean.push(read.clat.mean)
        h.latencyP95.push(read.clat.percentile["95.000000"])
        h.latencyP05.push(read.clat.percentile["5.000000"])
        h.iops.push(read.iops)
        return h
      }, {iops: [], concurrency: [], latencyMean: [], latencyP95: [], latencyP05: []})
      this.graph(results)
    },
    async processFile(file) {
      switch(file.type) {
        case 'text/csv': this.processCSV(await file.text()); break;
        case 'application/json': this.processJSON(await file.text()); break;
      }
    },
  },

  data: () => ({
    latencyIOPS: undefined,
    latencyConcurrency: undefined
  }),
};
</script>
