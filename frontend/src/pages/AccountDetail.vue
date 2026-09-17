<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getJSON, postJSON, putJSON } from '../api'
import SegmentTable from '../components/SegmentTable.vue'

const route = useRoute()
const data = ref(null)
const bill = ref(null)
const peak = ref(false)
const trialPeriod = ref('')
const saveMsg = ref('')

// demand-cap maintenance form
const form = ref({ period: '', demand_kw: '', threshold_kw: '', conversion_factor: 2 })
const formError = ref(null)

const account = computed(() => data.value?.account)
const caps = computed(() => data.value?.demand_caps || [])

const load = async () => {
  data.value = await getJSON(`/api/accounts/${route.params.id}`)
  trialPeriod.value = caps.value[0]?.period || ''
  saveMsg.value = ''
  await runBill()
}

const runBill = async () => {
  bill.value = null
  const r = data.value.readings[0]
  if (!r) return
  const body = {
    account_id: +route.params.id,
    kwh: r.kwh,
    peak: peak.value,
    persist: false,
  }
  if (trialPeriod.value) body.period = trialPeriod.value
  bill.value = await postJSON('/api/bill', body)
}

const resetForm = (cap) => {
  form.value = cap
    ? { period: cap.period, demand_kw: cap.demand_kw, threshold_kw: cap.threshold_kw, conversion_factor: cap.conversion_factor }
    : { period: '', demand_kw: '', threshold_kw: '', conversion_factor: 2 }
  formError.value = null
}
resetForm()

const editCap = (cap) => resetForm(cap)

const saveCap = async () => {
  formError.value = null
  saveMsg.value = ''
  try {
    await putJSON(
      `/api/accounts/${route.params.id}/demand-caps/${form.value.period}`,
      {
        demand_kw: +form.value.demand_kw,
        threshold_kw: +form.value.threshold_kw,
        conversion_factor: +form.value.conversion_factor,
      },
    )
    saveMsg.value = `账期 ${form.value.period} 参数已保存`
    await load()
    resetForm()
  } catch (e) {
    formError.value = e
  }
}

onMounted(load)
watch(() => route.params.id, load)
</script>
<template>
  <div class="page" v-if="account">
    <h1>{{ account.name }}</h1>
    <p class="muted">表号 {{ account.meter_no }} · {{ account.note }}</p>

    <div class="panel">
      <h3>需量封顶参数</h3>
      <table v-if="caps.length">
        <thead><tr><th>账期</th><th>需量(kW)</th><th>封顶阈值(kW)</th><th>折算系数</th><th>更新时间</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in caps" :key="c.period">
            <td>{{ c.period }}</td>
            <td>{{ c.demand_kw }}</td>
            <td>{{ c.threshold_kw }}</td>
            <td>{{ c.conversion_factor }}</td>
            <td class="muted">{{ c.updated_at }}</td>
            <td><a href="#" @click.prevent="editCap(c)">编辑</a></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">尚未维护任何账期的需量参数</p>

      <div class="cap-form">
        <label>账期 <input v-model="form.period" placeholder="YYYY-MM" /></label>
        <label>需量读数(kW) <input type="number" v-model="form.demand_kw" min="0" step="0.01" /></label>
        <label>封顶阈值(kW) <input type="number" v-model="form.threshold_kw" min="0" step="0.01" /></label>
        <label>超额折算系数 <input type="number" v-model="form.conversion_factor" min="0" step="0.01" /></label>
        <button @click="saveCap">录入 / 更新</button>
      </div>
      <p v-if="formError" class="err">
        <span class="err-code">[{{ formError.code || 'ERROR' }}]</span>
        字段 <code>{{ formError.field || '-' }}</code>：{{ formError.message }}
      </p>
      <p v-if="saveMsg" class="ok">{{ saveMsg }}</p>
    </div>

    <div class="panel">
      <h3>最近抄表试算</h3>
      <label><input type="checkbox" v-model="peak" @change="runBill" /> 尖峰</label>
      <label class="period-pick" v-if="caps.length">
        账期
        <select v-model="trialPeriod" @change="runBill">
          <option value="">不套封顶</option>
          <option v-for="c in caps" :key="c.period" :value="c.period">{{ c.period }}</option>
        </select>
      </label>
      <button @click="runBill">刷新</button>

      <div v-if="bill?.demand_cap" class="cap-banner" :class="{ on: bill.demand_cap.capped }">
        <template v-if="bill.demand_cap.capped">
          ⚠️ 触发封顶：需量 {{ bill.demand_cap.demand_kw }} kW &gt; 阈值 {{ bill.demand_cap.threshold_kw }} kW，
          超额 {{ bill.demand_cap.excess_kw }} kW × 系数 {{ bill.demand_cap.conversion_factor }}
          = 附加电量 <strong>{{ bill.additional_kwh }}</strong> kWh
        </template>
        <template v-else>
          ✅ 未触发封顶：需量 {{ bill.demand_cap.demand_kw }} kW ≤ 阈值 {{ bill.demand_cap.threshold_kw }} kW，附加电量 0 kWh
        </template>
      </div>

      <div v-if="bill?.demand_cap" class="split">
        <span>基础电量 <strong>{{ bill.base_kwh }}</strong> kWh</span>
        <span>附加电量 <strong>{{ bill.additional_kwh }}</strong> kWh</span>
        <span>合并净电量 <strong>{{ bill.net_kwh }}</strong> kWh</span>
        <span>合计 <strong class="hero-num" style="font-size:1.5rem">¥{{ bill.total }}</strong></span>
      </div>
      <p v-else-if="bill">
        合计 <strong class="hero-num" style="font-size:1.5rem">¥{{ bill.total }}</strong>
        <span class="muted">（未套账期封顶）</span>
      </p>
      <SegmentTable :rows="bill?.segments || []" />
    </div>
  </div>
</template>
<style scoped>
.cap-form { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: end; margin-top: 0.9rem; }
.cap-form label { display: flex; flex-direction: column; font-size: 0.85rem; gap: 0.25rem; }
.cap-form input { width: 9rem; }
.period-pick { margin-left: 1rem; }
.err { color: #ff8a8a; margin-top: 0.6rem; }
.err-code { font-weight: 700; }
.ok { color: var(--accent); margin-top: 0.6rem; }
.cap-banner {
  margin: 0.75rem 0; padding: 0.6rem 0.8rem; border-radius: 8px;
  background: color-mix(in srgb, var(--muted) 25%, transparent);
}
.cap-banner.on { background: color-mix(in srgb, #e8a13d 25%, transparent); }
.split { display: flex; flex-wrap: wrap; gap: 1.25rem; margin: 0.5rem 0 0.9rem; }
</style>
