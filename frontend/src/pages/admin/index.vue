<template>
  <AppShell
    active-path="/pages/admin/index"
    eyebrow="Admin"
    title="管理员控制台"
    subtitle="用户、充值、邀请码、题库 Provider 和系统设置都从这里集中维护。"
  >
    <template #actions>
      <button class="cx-inline-btn" :disabled="loading" @click="loadPage">
        {{ loading ? "刷新中..." : "刷新控制台" }}
      </button>
    </template>

    <view v-if="errorMessage" class="cx-alert page-alert">{{ errorMessage }}</view>
    <view v-if="successMessage" class="cx-success page-alert">{{ successMessage }}</view>

    <LoadingSpinner v-if="loading && !initialized" text="加载控制台..." />

    <template v-if="initialized">
    <view class="cx-grid metrics-grid">
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">用户数</text>
        <text class="cx-metric-value">{{ users.length }}</text>
        <text class="cx-field-hint">当前平台用户总数</text>
      </view>
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">运行中任务</text>
        <text class="cx-metric-value">{{ runningTaskCount }}</text>
        <text class="cx-field-hint">管理员可见的全局运行数</text>
      </view>
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">待审核充值</text>
        <text class="cx-metric-value">{{ pendingRechargeCount }}</text>
        <text class="cx-field-hint">等待审批的充值申请</text>
      </view>
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">有效邀请码</text>
        <text class="cx-metric-value">{{ activeInviteCount }}</text>
        <text class="cx-field-hint">仍可使用的邀请码条目</text>
      </view>
    </view>

    <view class="cx-grid cx-grid--double page-grid">
      <view class="cx-panel cx-panel--strong">
        <text class="cx-section-label">用户管理</text>
        <text class="cx-panel-title">角色、激活状态与强制改密</text>
        <view v-if="users.length" class="cx-list">
          <view v-for="user in users" :key="user.id" class="cx-list-item">
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">{{ user.display_name || user.username }}</text>
                <text class="cx-item-meta">
                  {{ user.username }} · {{ user.email }} · {{ user.role }}
                </text>
              </view>
              <text :class="['status-pill', user.is_active ? 'status-pill--ok' : 'status-pill--bad']">
                {{ user.is_active ? "已启用" : "已停用" }}
              </text>
            </view>
            <view class="action-row">
              <button class="cx-inline-btn" :disabled="busyAction" @click="toggleUserRole(user)">
                {{ user.role === "admin" ? "降为普通用户" : "提升为管理员" }}
              </button>
              <button class="cx-inline-btn" :disabled="busyAction" @click="toggleUserActive(user)">
                {{ user.is_active ? "停用" : "启用" }}
              </button>
              <button class="cx-inline-btn" :disabled="busyAction" @click="togglePasswordReset(user)">
                {{ user.must_change_password ? "取消强制改密" : "要求改密" }}
              </button>
            </view>
          </view>
        </view>
        <EmptyState v-else title="暂无用户" description="暂无用户数据。" />
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">充值审核</text>
        <text class="cx-panel-title">审批用户积分申请</text>
        <view v-if="rechargeOrders.length" class="cx-list">
          <view v-for="order in rechargeOrders" :key="order.id" class="cx-list-item">
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">订单 #{{ order.id }}</text>
                <text class="cx-item-meta">
                  用户 {{ order.user_id }} · {{ formatMoneyCents(order.amount_cents) }} / {{ order.requested_credits }} 积分
                </text>
              </view>
              <text :class="['status-pill', rechargeStatusClass(order.status)]">
                {{ formatRechargeStatus(order.status) }}
              </text>
            </view>
            <view class="action-row" v-if="order.status === 'pending'">
              <button class="cx-inline-btn" :disabled="busyAction" @click="reviewOrder(order.id, 'approved')">
                通过
              </button>
              <button class="cx-danger-btn" :disabled="busyAction" @click="reviewOrder(order.id, 'rejected')">
                拒绝
              </button>
            </view>
          </view>
        </view>
        <EmptyState v-else title="无待审核" description="当前没有待审核订单。" />
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">邀请码</text>
        <text class="cx-panel-title">新增或关闭邀请码</text>
        <view class="cx-form">
          <view>
            <text class="cx-field-label">邀请码</text>
            <input v-model="inviteForm.code" class="cx-input" />
          </view>
          <view>
            <text class="cx-field-label">最大使用次数</text>
            <input v-model="inviteForm.max_uses" class="cx-input" type="number" />
          </view>
          <view>
            <text class="cx-field-label">赠送积分</text>
            <input v-model="inviteForm.bonus_credits" class="cx-input" type="number" />
          </view>
          <button class="cx-primary-btn" :disabled="busyAction" @click="submitInvite">
            创建邀请码
          </button>
        </view>

        <view class="cx-list invite-list" v-if="invites.length">
          <view v-for="invite in invites" :key="invite.id" class="cx-list-item">
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">{{ invite.code }}</text>
                <text class="cx-item-meta">
                  已用 {{ invite.used_count }} / {{ invite.max_uses }} · 奖励 {{ invite.bonus_credits }}
                </text>
              </view>
              <text :class="['status-pill', invite.is_active ? 'status-pill--ok' : 'status-pill--bad']">
                {{ invite.is_active ? "有效" : "关闭" }}
              </text>
            </view>
            <button
              v-if="invite.is_active"
              class="cx-danger-btn"
              :disabled="busyAction"
              @click="disableInvite(invite.id)"
            >
              关闭邀请码
            </button>
          </view>
        </view>
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">题库 Provider</text>
        <text class="cx-panel-title">新增默认题库通道</text>
        <view class="cx-form">
          <view>
            <text class="cx-field-label">名称</text>
            <input v-model="providerForm.name" class="cx-input" />
          </view>
          <view>
            <text class="cx-field-label">类型</text>
            <view class="provider-type-grid">
              <button
                v-for="type in providerTypes"
                :key="type"
                :class="['cx-nav-btn', providerForm.provider_type === type ? 'cx-nav-btn--active' : '']"
                @click="providerForm.provider_type = type"
              >
                {{ type }}
              </button>
            </view>
          </view>
          <view>
            <text class="cx-field-label">优先级</text>
            <input v-model="providerForm.priority" class="cx-input" type="number" />
          </view>
          <view>
            <text class="cx-field-label">配置 JSON</text>
            <textarea v-model="providerForm.config_json" class="cx-textarea" />
          </view>
          <button class="cx-primary-btn" :disabled="busyAction" @click="submitProvider">
            保存 Provider
          </button>
        </view>

        <view class="cx-list invite-list" v-if="providers.length">
          <view v-for="provider in providers" :key="provider.id" class="cx-list-item">
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">{{ provider.name }}</text>
                <text class="cx-item-meta">
                  {{ provider.provider_type }} · priority {{ provider.priority }}
                </text>
              </view>
              <text :class="['status-pill', provider.is_active ? 'status-pill--ok' : 'status-pill--bad']">
                {{ provider.is_active ? "启用" : "停用" }}
              </text>
            </view>
          </view>
        </view>
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">系统设置</text>
        <text class="cx-panel-title">更新平台级配置</text>
        <view class="cx-form">
          <view>
            <text class="cx-field-label">设置键</text>
            <input v-model="settingForm.key" class="cx-input" placeholder="例如 platform" />
          </view>
          <view>
            <text class="cx-field-label">设置值 JSON</text>
            <textarea v-model="settingForm.value_json" class="cx-textarea" />
          </view>
          <button class="cx-primary-btn" :disabled="busyAction" @click="submitSetting">
            保存系统设置
          </button>
        </view>

        <view class="cx-list invite-list" v-if="systemSettings.length">
          <view
            v-for="setting in systemSettings"
            :key="setting.key"
            class="cx-list-item"
            @click="prefillSetting(setting)"
          >
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">{{ setting.key }}</text>
                <text class="cx-item-meta">{{ formatDateTime(setting.updated_at) }}</text>
              </view>
              <text class="status-pill status-pill--warn">点我编辑</text>
            </view>
          </view>
        </view>
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">全局任务</text>
        <text class="cx-panel-title">管理员视角的运行列表</text>
        <view v-if="tasks.length" class="cx-list">
          <view v-for="task in tasks.slice(0, 8)" :key="task.id" class="cx-list-item">
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">运行 #{{ task.id }}</text>
                <text class="cx-item-meta">
                  用户 {{ task.user_id }} · 账号 {{ task.account_id }} · 课程 {{ task.course_ids?.join(", ") || "未选" }}
                </text>
              </view>
              <text :class="['status-pill', taskStatusClass(task.status)]">
                {{ formatRunStatus(task.status) }}
              </text>
            </view>
            <text class="cx-item-meta">{{ formatDateTime(task.created_at) }}</text>
          </view>
        </view>
        <EmptyState v-else title="无任务" description="当前没有学习任务。" />
      </view>
    </view>
    </template>
  </AppShell>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";

import AppShell from "../../components/AppShell.vue";
import LoadingSpinner from "../../components/LoadingSpinner.vue";
import EmptyState from "../../components/EmptyState.vue";
import {
  createInvite,
  createTikuProvider,
  deleteInvite,
  listAdminTasks,
  listInvites,
  listRechargeOrders,
  listSystemSettings,
  listTikuProviders,
  listUsers,
  reviewRechargeOrder,
  updateSystemSetting,
  updateUser,
} from "../../api/admin";
import { useSessionStore } from "../../store/session";
import { requireSession } from "../../utils/access";
import {
  extractErrorMessage,
  formatDateTime,
  formatMoneyCents,
  formatRechargeStatus,
  formatRunStatus,
} from "../../utils/display";
import { parseJsonInput, stringifyJson } from "../../utils/json";

const session = useSessionStore();

const loading = ref(false);
const initialized = ref(false);
const busyAction = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const users = ref([]);
const tasks = ref([]);
const rechargeOrders = ref([]);
const invites = ref([]);
const providers = ref([]);
const systemSettings = ref([]);

const providerTypes = ["yanxi", "like", "adapter", "openai_compat", "siliconflow"];

const inviteForm = reactive({
  code: "",
  max_uses: "1",
  bonus_credits: "0",
});

const providerForm = reactive({
  name: "",
  provider_type: "openai_compat",
  priority: "100",
  config_json: '{\n  "api_key": ""\n}',
});

const settingForm = reactive({
  key: "",
  value_json: '{\n  "invite_only": false\n}',
});

const runningTaskCount = computed(
  () => tasks.value.filter((task) => ["queued", "running", "stopping"].includes(task.status)).length,
);
const pendingRechargeCount = computed(
  () => rechargeOrders.value.filter((order) => order.status === "pending").length,
);
const activeInviteCount = computed(() => invites.value.filter((invite) => invite.is_active).length);

onShow(async () => {
  await loadPage();
});

async function loadPage() {
  if (!(await requireSession(session, { admin: true, allowPasswordReset: false }))) {
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  try {
    const [userData, taskData, orderData, inviteData, providerData, settingsData] = await Promise.all([
      listUsers(),
      listAdminTasks(),
      listRechargeOrders(),
      listInvites(),
      listTikuProviders(),
      listSystemSettings(),
    ]);
    users.value = userData;
    tasks.value = taskData;
    rechargeOrders.value = orderData;
    invites.value = inviteData;
    providers.value = providerData;
    systemSettings.value = settingsData;
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    loading.value = false;
    initialized.value = true;
  }
}

async function toggleUserRole(user) {
  await runAction(async () => {
    await updateUser(user.id, { role: user.role === "admin" ? "user" : "admin" });
    await loadPage();
    successMessage.value = "用户角色已更新。";
  });
}

async function toggleUserActive(user) {
  await runAction(async () => {
    await updateUser(user.id, { is_active: !user.is_active });
    await loadPage();
    successMessage.value = "用户启用状态已更新。";
  });
}

async function togglePasswordReset(user) {
  await runAction(async () => {
    await updateUser(user.id, { must_change_password: !user.must_change_password });
    await loadPage();
    successMessage.value = "强制改密标记已更新。";
  });
}

async function reviewOrder(orderId, status) {
  await runAction(async () => {
    await reviewRechargeOrder(orderId, {
      status,
      review_note: `reviewed-in-web-${status}`,
    });
    await loadPage();
    successMessage.value = "充值订单已审核。";
  });
}

async function submitInvite() {
  if (!inviteForm.code.trim()) {
    errorMessage.value = "邀请码不能为空";
    return;
  }
  await runAction(async () => {
    await createInvite({
      code: inviteForm.code.trim(),
      max_uses: Number(inviteForm.max_uses || "1"),
      bonus_credits: Number(inviteForm.bonus_credits || "0"),
    });
    inviteForm.code = "";
    inviteForm.max_uses = "1";
    inviteForm.bonus_credits = "0";
    await loadPage();
    successMessage.value = "邀请码已创建。";
  });
}

async function disableInvite(inviteId) {
  await runAction(async () => {
    await deleteInvite(inviteId);
    await loadPage();
    successMessage.value = "邀请码已关闭。";
  });
}

async function submitProvider() {
  if (!providerForm.name.trim()) {
    errorMessage.value = "Provider 名称不能为空";
    return;
  }
  await runAction(async () => {
    await createTikuProvider({
      name: providerForm.name.trim(),
      provider_type: providerForm.provider_type,
      config: parseJsonInput(providerForm.config_json, {}),
      priority: Number(providerForm.priority || "100"),
      is_active: true,
    });
    providerForm.name = "";
    providerForm.priority = "100";
    providerForm.config_json = '{\n  "api_key": ""\n}';
    await loadPage();
    successMessage.value = "题库 Provider 已保存。";
  });
}

async function submitSetting() {
  if (!settingForm.key.trim()) {
    errorMessage.value = "设置键不能为空";
    return;
  }
  await runAction(async () => {
    await updateSystemSetting(settingForm.key.trim(), {
      value: parseJsonInput(settingForm.value_json, {}),
    });
    await loadPage();
    successMessage.value = "系统设置已保存。";
  });
}

function prefillSetting(setting) {
  settingForm.key = setting.key;
  settingForm.value_json = stringifyJson(setting.value || {});
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

function taskStatusClass(status) {
  if (status === "succeeded") {
    return "status-pill--ok";
  }
  if (status === "failed" || status === "cancelled") {
    return "status-pill--bad";
  }
  return "status-pill--warn";
}

function rechargeStatusClass(status) {
  if (status === "approved") {
    return "status-pill--ok";
  }
  if (status === "rejected") {
    return "status-pill--bad";
  }
  return "status-pill--warn";
}
</script>

<style>
.metrics-grid {
  margin-top: 24rpx;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  min-height: 220rpx;
  justify-content: space-between;
}

.page-grid,
.page-alert {
  margin-top: 24rpx;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 10rpx 18rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
  font-weight: 700;
}

.status-pill--warn {
  background: rgba(157, 79, 31, 0.12);
  color: var(--cx-accent-dark);
}

.status-pill--ok {
  background: rgba(48, 82, 67, 0.12);
  color: var(--cx-olive);
}

.status-pill--bad {
  background: rgba(157, 47, 47, 0.1);
  color: var(--cx-alert);
}

.action-row,
.provider-type-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.invite-list {
  margin-top: 20rpx;
}

@media (max-width: 959px) {
  .metrics-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
