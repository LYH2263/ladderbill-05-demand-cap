<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { currentPeriod, getJSON, postJSON, putJSON } from '../api'
import SegmentTable from '../components/SegmentTable.vue'
import DemandCapCard from '../components/DemandCapCard.vue'

const route = useRoute()
const data = ref(null)
const probe = ref(null)
const peak = ref(false)
const period = ref(currentPeriod())
const form = ref({ demand_kw: '', cap_kw: '', convert_coef: 3 })
const error = ref(null)
const saving = ref(false)

const FIELD_LABEL = {
  demand_kw: '账期需量',
  cap_kw: '封顶阈值',
  convert_coef: '折算系数',
  period: '账期',
}

const account = computed(() => data.value?.account)
const latestReading = computed(() => data.value?.readings?.[0] || null)
const capRows = computed(() => data.value?.demand_caps || [])

const fillFormFromPeriod = () => {
  const row = capRows.value.find((c) => c.period === period.value)
  if (row) {
    form.value = {
      demand_kw: row.demand_kw,
      cap_kw: row.cap_kw,
      convert_coef: row.convert_coef,
    }
  }
}

const runProbe = async () => {
  const r = latestReading.value
  if (!r) { probe.value = null; return }
  probe.value = await postJSON('/api/demand-cap/probe', {
    account_id: +route.params.id,
    period: period.value,
    kwh: r.kwh,
    peak: peak.value,
  })
}

const load = async () => {
  error.value = null
  data.value = await getJSON(`/api/accounts/${route.params.id}`)
  peak.value = !!data.value.readings[0]?.peak
  fillFormFromPeriod()
  await runProbe()
}

const save = async () => {
  error.value = null
  saving.value = true
  try {
    await putJSON(`/api/accounts/${route.params.id}/demand-caps/${period.value}`, {
      demand_kw: Number(form.value.demand_kw),
      cap_kw: Number(form.value.cap_kw),
      convert_coef: Number(form.value.convert_coef),
    })
    await load()
  } catch (e) {
    const label = e.field ? FIELD_LABEL[e.field] || e.field : ''
    error.value = e.message ? `[${e.code || '错误'}${label ? ' · ' + label : ''}] ${e.message}` : String(e)
  } finally {
    saving.value = false
  }
}

onMounted(load)
watch(() => route.params.id, load)
watch(peak, runProbe)
</script>

<template>
  <div class="page" v-if="account">
    <h1>{{ account.name }}</h1>
    <p class="muted">表号 {{ account.meter_no }} · {{ account.note }}</p>

    <div class="panel">
      <h3>需量封顶参数</h3>
      <div class="form-row">
        <label>账期
          <input type="month" v-model="period" @change="fillFormFromPeriod(); runProbe()" />
        </label>
        <label>账期需量(kW)
          <input type="number" v-model="form.demand_kw" step="0.1" min="0" />
        </label>
        <label>封顶阈值(kW)
          <input type="number" v-model="form.cap_kw" step="0.1" min="0" />
        </label>
        <label>超额折算系数
          <input type="number" v-model="form.convert_coef" step="0.1" min="0" max="10" />
        </label>
        <button :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存/更新' }}</button>
      </div>
      <p v-if="error" class="err">{{ error }}</p>
      <p class="muted hint">需量不能为负；阈值必须大于 0；折算系数合理范围 0~10。超额需量 × 系数 = 附加电量。</p>
      <table v-if="capRows.length" class="cap-table">
        <thead><tr><th>账期</th><th>需量(kW)</th><th>阈值(kW)</th><th>系数</th></tr></thead>
        <tbody>
          <tr v-for="c in capRows" :key="c.period">
            <td>{{ c.period }}</td><td>{{ c.demand_kw }}</td><td>{{ c.cap_kw }}</td><td>{{ c.convert_coef }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h3>最近抄表只读试算</h3>
      <label><input type="checkbox" v-model="peak" /> 尖峰</label>
      <button class="ghost" @click="runProbe">刷新试算</button>
      <DemandCapCard v-if="probe" :cap="probe.demand_cap" />
      <div v-if="probe" class="qty-grid">
        <div><div class="muted">基础电量</div><strong>{{ probe.base_kwh }} kWh</strong></div>
        <div><div class="muted">附加电量</div><strong>{{ probe.extra_kwh }} kWh</strong></div>
        <div><div class="muted">合并净电量</div><strong>{{ probe.net_kwh }} kWh</strong></div>
        <div><div class="muted">合计</div><strong class="hero-num" style="font-size:1.5rem">¥{{ probe.total }}</strong></div>
      </div>
      <SegmentTable :rows="probe?.segments || []" />
    </div>
  </div>
</template>
<style scoped>
.form-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: end; margin: 0.5rem 0; }
input[type=number] { width: 7rem; margin-left: 0.3rem; }
.err { color: #ff7a7a; margin: 0.5rem 0 0; }
.hint { margin-top: 0.6rem; }
.cap-table { margin-top: 0.75rem; }
.qty-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin: 0.5rem 0 1rem; }
.qty-grid > div { background: #0d1612; padding: 0.6rem 0.75rem; border-radius: 8px; }
.ghost { background: transparent; border: 1px solid var(--accent); color: var(--accent); margin-left: 0.75rem; }
</style>
