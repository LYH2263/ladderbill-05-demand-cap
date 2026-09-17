<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
import TierLadder from '../components/TierLadder.vue'
import SegmentTable from '../components/SegmentTable.vue'

const accounts = ref([])
const accountId = ref(null)
const period = ref('')
const kwh = ref(220)
const peak = ref(false)
const result = ref(null)
const err = ref(null)

onMounted(async () => {
  accounts.value = (await getJSON('/api/accounts')).items
  accountId.value = accounts.value[0]?.id ?? null
})

const showError = (e) => {
  result.value = null
  err.value = e
}

const trial = async () => {
  err.value = null
  try {
    result.value = await postJSON('/api/demand-cap/trial', {
      account_id: accountId.value,
      period: period.value,
      kwh: kwh.value,
      peak: peak.value,
    })
  } catch (e) { showError(e) }
}

const run = async () => {
  err.value = null
  try {
    const body = { account_id: accountId.value, kwh: kwh.value, peak: peak.value, persist: true }
    if (period.value) body.period = period.value
    result.value = await postJSON('/api/bill', body)
  } catch (e) { showError(e) }
}
</script>
<template>
  <div class="page work">
    <h1>测算工作台</h1>
    <div class="panel form-row">
      <label>户号
        <select v-model="accountId">
          <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}（{{ a.meter_no }}）</option>
        </select>
      </label>
      <label>账期 <input v-model="period" placeholder="YYYY-MM" /></label>
      <label>电量(kWh) <input type="number" v-model.number="kwh" min="0" step="1" /></label>
      <label><input type="checkbox" v-model="peak" /> 尖峰系数</label>
      <button class="secondary" @click="trial" :disabled="!period">封顶试算（只读）</button>
      <button @click="run">计算并入库</button>
    </div>
    <p class="muted hint">
      填写账期后可做只读封顶试算（不产生计费记录、不改户参数）；附加电量会并入净电量后再走阶梯与尖峰。
    </p>

    <p v-if="err" class="err">
      <span class="err-code">[{{ err.code || 'ERROR' }}]</span>
      <template v-if="err.field">字段 <code>{{ err.field }}</code>：</template>{{ err.message }}
    </p>

    <div v-if="result" class="panel">
      <div v-if="result.demand_cap" class="cap-banner" :class="{ on: result.demand_cap.capped }">
        <template v-if="result.demand_cap.capped">
          ⚠️ 触发封顶：需量 {{ result.demand_cap.demand_kw }} kW &gt; 阈值 {{ result.demand_cap.threshold_kw }} kW，
          超额 {{ result.demand_cap.excess_kw }} kW × 折算系数 {{ result.demand_cap.conversion_factor }}
          = 附加电量 <strong>{{ result.additional_kwh }}</strong> kWh
        </template>
        <template v-else>
          ✅ 未触发封顶：需量 {{ result.demand_cap.demand_kw }} ≤ 阈值 {{ result.demand_cap.threshold_kw }} kW，附加电量为 0
        </template>
        <span class="muted">（附加量来源：{{ result.source === 'trial' ? '试算覆盖参数' : '已维护账期参数' }}）</span>
      </div>

      <div v-if="result.demand_cap" class="split">
        <span>基础电量 <strong>{{ result.base_kwh }}</strong></span>
        <span>附加电量 <strong>{{ result.additional_kwh }}</strong></span>
        <span>合并净电量 <strong>{{ result.net_kwh }}</strong> kWh</span>
        <span>合计 ¥{{ result.total }}</span>
        <span v-if="result.run_id" class="muted">记录#{{ result.run_id }}</span>
        <span v-else class="muted">只读试算·未入库</span>
      </div>
      <p v-else>合计 ¥{{ result.total }} <span class="muted">记录#{{ result.run_id }}</span></p>

      <TierLadder :segments="result.segments" />
      <SegmentTable :rows="result.segments" />
    </div>
  </div>
</template>
<style scoped>
.form-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: end; }
input[type=number] { width: 6rem; margin-left: 0.35rem; }
input[placeholder] { width: 8rem; }
select { margin-left: 0.35rem; }
.hint { font-size: 0.85rem; }
.err { color: #ff8a8a; }
.err-code { font-weight: 700; }
.cap-banner {
  margin-bottom: 0.75rem; padding: 0.6rem 0.8rem; border-radius: 8px;
  background: color-mix(in srgb, var(--muted) 25%, transparent);
}
.cap-banner.on { background: color-mix(in srgb, #e8a13d 25%, transparent); }
.split { display: flex; flex-wrap: wrap; gap: 1.25rem; margin-bottom: 0.9rem; }
.secondary { background: color-mix(in srgb, var(--accent) 65%, #111); }
</style>
