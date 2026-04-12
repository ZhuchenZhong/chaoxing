<template>
  <AppShell
    active-path="/pages/settings/index"
    eyebrow="Settings"
    title="个人与执行设置"
    subtitle="这里集中处理个人资料、学习策略、题库配置、密码轮换和充值申请。"
  >
    <template #actions>
      <button class="cx-inline-btn" :disabled="loading" @click="loadPage">
        {{ loading ? "刷新中..." : "刷新设置" }}
      </button>
    </template>

    <view v-if="errorMessage" class="cx-alert page-alert">{{ errorMessage }}</view>
    <view v-if="successMessage" class="cx-success page-alert">{{ successMessage }}</view>

    <view class="cx-grid metrics-grid">
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">当前积分</text>
        <text class="cx-metric-value">{{ workspace.wallet?.balance ?? 0 }}</text>
        <text class="cx-field-hint">用于任务和平台功能消耗</text>
      </view>
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">最近一次流水</text>
        <text class="cx-metric-value metric-mini">
          {{ recentTransaction ? formatDelta(recentTransaction.delta) : "无" }}
        </text>
        <text class="cx-field-hint">
          {{ recentTransaction ? formatDateTime(recentTransaction.created_at) : "暂无记录" }}
        </text>
      </view>
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">默认倍率</text>
        <text class="cx-metric-value metric-mini">{{ studyForm.speed || "1.0" }}</text>
        <text class="cx-field-hint">来自当前默认学习 profile</text>
      </view>
    </view>

    <view class="cx-grid cx-grid--double page-grid">
      <view class="cx-grid settings-stack">
        <view class="cx-panel cx-panel--strong">
          <text class="cx-section-label">个人资料</text>
          <text class="cx-panel-title">登录标识与展示信息</text>
          <view class="cx-form">
            <view>
              <text class="cx-field-label">用户名</text>
              <input v-model="profileForm.username" class="cx-input" />
            </view>
            <view>
              <text class="cx-field-label">邮箱</text>
              <input v-model="profileForm.email" class="cx-input" />
            </view>
            <view>
              <text class="cx-field-label">显示名称</text>
              <input v-model="profileForm.display_name" class="cx-input" />
            </view>
            <button class="cx-primary-btn" :disabled="busyAction" @click="saveProfile">
              保存资料
            </button>
          </view>
        </view>

        <view class="cx-panel">
          <text class="cx-section-label">学习配置</text>
          <text class="cx-panel-title">默认学习策略</text>
          <view class="cx-form">
            <view>
              <text class="cx-field-label">倍速</text>
              <input v-model="studyForm.speed" class="cx-input" type="digit" />
            </view>
            <view>
              <text class="cx-field-label">未开放章节策略</text>
              <view class="auth-type-row">
                <button
                  :class="['cx-nav-btn', studyForm.notopen_action === 'retry' ? 'cx-nav-btn--active' : '']"
                  @click="studyForm.notopen_action = 'retry'"
                >
                  重试
                </button>
                <button
                  :class="['cx-nav-btn', studyForm.notopen_action === 'continue' ? 'cx-nav-btn--active' : '']"
                  @click="studyForm.notopen_action = 'continue'"
                >
                  跳过
                </button>
              </view>
            </view>
            <view>
              <text class="cx-field-label">提交配置 JSON</text>
              <textarea v-model="studyForm.submit_config_json" class="cx-textarea" />
            </view>
            <button class="cx-primary-btn" :disabled="busyAction" @click="saveStudyConfig">
              保存学习配置
            </button>
          </view>
        </view>

        <view class="cx-panel">
          <text class="cx-section-label">题库配置</text>
          <text class="cx-panel-title">默认题库路由和模型参数</text>
          <view class="cx-form">
            <view>
              <text class="cx-field-label">题库配置 JSON</text>
              <textarea v-model="tikuConfigJson" class="cx-textarea" />
            </view>
            <button class="cx-primary-btn" :disabled="busyAction" @click="saveTikuConfig">
              保存题库配置
            </button>
          </view>
        </view>

        <view class="cx-panel">
          <text class="cx-section-label">通知配置</text>
          <text class="cx-panel-title">学习任务完成后的推送通道</text>
          <view class="cx-form">
            <view>
              <text class="cx-field-label">通知提供者 JSON</text>
              <text class="cx-field-hint">
                每条记录包含 provider（bark / pushplus / server_chan / dingtalk / custom_webhook）、enabled、name、settings_json 字段。
              </text>
              <textarea v-model="notificationConfigJson" class="cx-textarea" />
            </view>
            <view class="action-row">
              <button class="cx-primary-btn" :disabled="busyAction" @click="saveNotificationConfig">
                保存通知配置
              </button>
              <button class="cx-ghost-btn" :disabled="busyAction" @click="testNotification">
                发送测试
              </button>
            </view>
          </view>
        </view>
      </view>

      <view class="cx-grid settings-stack">
        <view class="cx-panel">
          <text class="cx-section-label">密码轮换</text>
          <text class="cx-panel-title">主动修改平台登录密码</text>
          <view class="cx-form">
            <view>
              <text class="cx-field-label">当前密码</text>
              <input v-model="passwordForm.current" class="cx-input" password />
            </view>
            <view>
              <text class="cx-field-label">新密码</text>
              <input v-model="passwordForm.next" class="cx-input" password />
            </view>
            <view>
              <text class="cx-field-label">确认新密码</text>
              <input v-model="passwordForm.confirm" class="cx-input" password />
            </view>
            <button class="cx-primary-btn" :disabled="busyAction" @click="savePassword">
              更新密码
            </button>
          </view>
        </view>

        <view class="cx-panel">
          <text class="cx-section-label">充值申请</text>
          <text class="cx-panel-title">提交待审核的积分申请</text>
          <view class="cx-form">
            <view>
              <text class="cx-field-label">金额（分）</text>
              <input v-model="rechargeForm.amount_cents" class="cx-input" type="number" />
            </view>
            <view>
              <text class="cx-field-label">申请积分</text>
              <input v-model="rechargeForm.requested_credits" class="cx-input" type="number" />
            </view>
            <view>
              <text class="cx-field-label">支付渠道</text>
              <input v-model="rechargeForm.payment_channel" class="cx-input" placeholder="alipay / wechat" />
            </view>
            <view>
              <text class="cx-field-label">支付单号</text>
              <input v-model="rechargeForm.payment_reference" class="cx-input" />
            </view>
            <view>
              <text class="cx-field-label">凭证路径</text>
              <input v-model="rechargeForm.proof_path" class="cx-input" />
            </view>
            <button class="cx-primary-btn" :disabled="busyAction" @click="submitRecharge">
              提交充值申请
            </button>
          </view>
        </view>

        <view class="cx-panel">
          <text class="cx-section-label">钱包流水</text>
          <text class="cx-panel-title">最近的积分变动</text>
          <view v-if="workspace.walletTransactions.length" class="cx-list">
            <view
              v-for="transaction in workspace.walletTransactions.slice(0, 8)"
              :key="transaction.id"
              class="cx-list-item"
            >
              <view class="cx-item-top">
                <view>
                  <text class="cx-item-title">{{ transaction.reason }}</text>
                  <text class="cx-item-meta">{{ formatDateTime(transaction.created_at) }}</text>
                </view>
                <text :class="['delta-chip', Number(transaction.delta) >= 0 ? 'delta-chip--up' : 'delta-chip--down']">
                  {{ formatDelta(transaction.delta) }}
                </text>
              </view>
              <text class="cx-item-meta">余额 {{ transaction.balance_after }}</text>
            </view>
          </view>
          <view v-else class="cx-empty">暂无钱包流水。</view>
        </view>
      </view>
    </view>
  </AppShell>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";

import AppShell from "../../components/AppShell.vue";
import { createRecharge } from "../../api/wallet";
import { getProfile, updateProfile } from "../../api/users";
import { useSessionStore } from "../../store/session";
import { useWorkspaceStore } from "../../store/workspace";
import { requireSession } from "../../utils/access";
import { extractErrorMessage, formatDateTime, formatDelta } from "../../utils/display";
import { parseJsonInput, stringifyJson } from "../../utils/json";

const session = useSessionStore();
const workspace = useWorkspaceStore();

const loading = ref(false);
const busyAction = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const profileForm = reactive({
  username: "",
  email: "",
  display_name: "",
});

const studyForm = reactive({
  speed: "1.0",
  notopen_action: "retry",
  submit_config_json: "{}",
});

const passwordForm = reactive({
  current: "",
  next: "",
  confirm: "",
});

const rechargeForm = reactive({
  amount_cents: "",
  requested_credits: "",
  payment_channel: "alipay",
  payment_reference: "",
  proof_path: "",
});

const tikuConfigJson = ref("{}");
const notificationConfigJson = ref("[]");
const recentTransaction = computed(() => workspace.walletTransactions[0] || null);

onShow(async () => {
  await loadPage();
});

async function loadPage() {
  if (!(await requireSession(session, { allowPasswordReset: false }))) {
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  try {
    const [profile] = await Promise.all([
      getProfile(),
      workspace.loadSettings(),
      workspace.loadWallet(),
      workspace.loadWalletHistory(),
      workspace.loadNotificationConfig(),
    ]);
    profileForm.username = profile.username || "";
    profileForm.email = profile.email || "";
    profileForm.display_name = profile.display_name || "";
    studyForm.speed = String(workspace.studyConfig?.speed ?? "1.0");
    studyForm.notopen_action = workspace.studyConfig?.notopen_action || "retry";
    studyForm.submit_config_json = stringifyJson(workspace.studyConfig?.submit_config || {});
    tikuConfigJson.value = stringifyJson(workspace.tikuConfig?.tiku_config || {});
    notificationConfigJson.value = stringifyJson(workspace.notificationConfig?.providers || []);
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

async function saveProfile() {
  await runAction(async () => {
    const updated = await updateProfile({
      username: profileForm.username.trim(),
      email: profileForm.email.trim(),
      display_name: profileForm.display_name.trim() || null,
    });
    session.user = updated;
    successMessage.value = "个人资料已更新。";
  });
}

async function saveStudyConfig() {
  await runAction(async () => {
    await workspace.saveStudyConfig({
      speed: Number(studyForm.speed || "1"),
      notopen_action: studyForm.notopen_action,
      submit_config: parseJsonInput(studyForm.submit_config_json, {}),
    });
    successMessage.value = "学习配置已保存。";
  });
}

async function saveTikuConfig() {
  await runAction(async () => {
    await workspace.saveTikuConfig({
      tiku_config: parseJsonInput(tikuConfigJson.value, {}),
    });
    successMessage.value = "题库配置已保存。";
  });
}

async function saveNotificationConfig() {
  await runAction(async () => {
    const providers = parseJsonInput(notificationConfigJson.value, []);
    await workspace.saveNotificationConfig({ providers });
    notificationConfigJson.value = stringifyJson(workspace.notificationConfig?.providers || []);
    successMessage.value = "通知配置已保存。";
  });
}

async function testNotification() {
  await runAction(async () => {
    const result = await workspace.sendTestNotification();
    const entries = Object.entries(result.results || {});
    if (!entries.length) {
      successMessage.value = "没有已启用的通知通道。";
      return;
    }
    const summary = entries.map(([k, v]) => `${k}: ${v ? "✓" : "✗"}`).join("，");
    successMessage.value = `测试结果 — ${summary}`;
  });
}

async function savePassword() {
  if (!passwordForm.current || !passwordForm.next) {
    errorMessage.value = "请完整填写密码信息";
    return;
  }
  if (passwordForm.next.length < 8) {
    errorMessage.value = "新密码至少需要 8 位";
    return;
  }
  if (passwordForm.next !== passwordForm.confirm) {
    errorMessage.value = "两次输入的新密码不一致";
    return;
  }
  await runAction(async () => {
    await session.rotatePassword(passwordForm.current, passwordForm.next);
    passwordForm.current = "";
    passwordForm.next = "";
    passwordForm.confirm = "";
    successMessage.value = "密码已更新。";
  });
}

async function submitRecharge() {
  if (!rechargeForm.amount_cents || !rechargeForm.requested_credits) {
    errorMessage.value = "金额和积分不能为空";
    return;
  }
  await runAction(async () => {
    await createRecharge({
      amount_cents: Number(rechargeForm.amount_cents),
      requested_credits: Number(rechargeForm.requested_credits),
      payment_channel: rechargeForm.payment_channel || null,
      payment_reference: rechargeForm.payment_reference || null,
      proof_path: rechargeForm.proof_path || null,
    });
    rechargeForm.amount_cents = "";
    rechargeForm.requested_credits = "";
    rechargeForm.payment_reference = "";
    rechargeForm.proof_path = "";
    await workspace.loadWalletHistory();
    successMessage.value = "充值申请已提交，等待管理员审核。";
  });
}

async function runAction(action) {
  busyAction.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    await action();
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    busyAction.value = false;
  }
}
</script>

<style>
.metrics-grid {
  margin-top: 24rpx;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metric-card {
  min-height: 220rpx;
  justify-content: space-between;
}

.metric-mini {
  font-size: 46rpx;
}

.page-grid,
.page-alert {
  margin-top: 24rpx;
}

.settings-stack {
  align-content: start;
}

.auth-type-row,
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.delta-chip {
  display: inline-flex;
  align-items: center;
  padding: 10rpx 18rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
  font-weight: 700;
}

.delta-chip--up {
  background: rgba(48, 82, 67, 0.12);
  color: var(--cx-olive);
}

.delta-chip--down {
  background: rgba(157, 47, 47, 0.1);
  color: var(--cx-alert);
}

@media (max-width: 959px) {
  .metrics-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
