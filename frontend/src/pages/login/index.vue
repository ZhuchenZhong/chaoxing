<template>
  <AppShell
    active-path="/pages/login/index"
    eyebrow="Primary Entrypoint"
    :title="pageTitle"
    :subtitle="pageSubtitle"
  >
    <view class="cx-grid cx-grid--double auth-layout">
      <view class="cx-panel cx-panel--strong">
        <text class="cx-panel-title">
          {{ session.needsPasswordReset ? "完成密码升级" : "登录新工作台" }}
        </text>
        <text class="cx-panel-subtitle">
          {{ session.needsPasswordReset ? "迁移用户需要先升级密码，之后才能进入账户和任务页面。" : "Web 端现在是唯一入口。登录后可以重绑超星账号、同步课程并发起学习任务。" }}
        </text>

        <view v-if="errorMessage" class="cx-alert">{{ errorMessage }}</view>
        <view v-if="successMessage" class="cx-success">{{ successMessage }}</view>

        <view v-if="session.needsPasswordReset" class="cx-form">
          <view>
            <text class="cx-field-label">当前密码</text>
            <input
              v-model="passwordForm.currentPassword"
              class="cx-input"
              password
              placeholder="输入当前密码"
            />
          </view>
          <view>
            <text class="cx-field-label">新密码</text>
            <input
              v-model="passwordForm.newPassword"
              class="cx-input"
              password
              placeholder="至少 8 位"
            />
          </view>
          <view>
            <text class="cx-field-label">确认新密码</text>
            <input
              v-model="passwordForm.confirmPassword"
              class="cx-input"
              password
              placeholder="再次输入新密码"
            />
          </view>
          <button class="cx-primary-btn" :disabled="submitting" @click="submitPasswordReset">
            {{ submitting ? "处理中..." : "保存新密码并进入工作台" }}
          </button>
        </view>

        <view v-else class="cx-form">
          <view>
            <text class="cx-field-label">用户名</text>
            <input
              v-model="loginForm.username"
              class="cx-input"
              placeholder="输入用户名"
            />
          </view>
          <view>
            <text class="cx-field-label">密码</text>
            <input
              v-model="loginForm.password"
              class="cx-input"
              password
              placeholder="输入密码"
            />
          </view>
          <button class="cx-primary-btn" :disabled="submitting" @click="submitLogin">
            {{ submitting ? "登录中..." : "进入工作台" }}
          </button>
          <view class="register-link" @click="goToRegister">
            <text>没有账号？立即注册</text>
          </view>
        </view>
      </view>

      <view class="cx-grid narrative-stack">
        <view class="cx-panel">
          <text class="cx-section-label">迁移说明</text>
          <text class="cx-panel-title">旧账户已经迁入，但凭据不会自动复用</text>
          <text class="cx-panel-subtitle">
            历史超星账户数据保留了关系和状态，但加密凭据不能直接复原。登录后需要到“超星账号”页重新绑定或重新校验。
          </text>
          <view class="bullet-list">
            <text class="bullet-item">Web 是当前唯一入口，CLI 只保留在 `bak/` 里供比对。</text>
            <text class="bullet-item">普通用户优先以移动浏览器体验设计，桌面端会增加信息密度。</text>
            <text class="bullet-item">任务进度采用事件落库和前端轮询，不依赖长连接。</text>
          </view>
        </view>

        <view class="cx-panel">
          <text class="cx-section-label">环境基线</text>
          <text class="cx-item-title">当前 API 基址</text>
          <text class="mono-line">{{ apiBaseUrl }}</text>
          <text class="cx-field-hint">
            需要切换环境时，直接设置 `VITE_API_BASE_URL`。
          </text>
        </view>
      </view>
    </view>
  </AppShell>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";

import AppShell from "../../components/AppShell.vue";
import { getApiBaseUrl } from "../../api/client";
import { useSessionStore } from "../../store/session";
import { extractErrorMessage } from "../../utils/display";

const session = useSessionStore();
const apiBaseUrl = getApiBaseUrl();
const submitting = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const loginForm = reactive({
  username: "",
  password: "",
});

const passwordForm = reactive({
  currentPassword: "",
  newPassword: "",
  confirmPassword: "",
});

const pageTitle = computed(() =>
  session.needsPasswordReset ? "完成迁移后的密码升级" : "Chaoxing Workbench",
);

const pageSubtitle = computed(() =>
  session.needsPasswordReset
    ? "先修改密码，再进入账号、课程和任务工作台。"
    : "统一登录、统一任务入口、统一账户管理。",
);

onShow(async () => {
  await session.bootstrap();
  if (session.isAuthenticated && !session.needsPasswordReset) {
    uni.reLaunch({ url: "/pages/index/index" });
  }
});

async function submitLogin() {
  if (!loginForm.username.trim() || !loginForm.password) {
    errorMessage.value = "用户名和密码不能为空";
    return;
  }

  submitting.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    await session.loginWithPassword(loginForm.username.trim(), loginForm.password);
    if (session.needsPasswordReset) {
      passwordForm.currentPassword = loginForm.password;
      successMessage.value = "登录成功，请先完成首次改密。";
      return;
    }
    uni.reLaunch({ url: "/pages/index/index" });
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    submitting.value = false;
  }
}

async function submitPasswordReset() {
  if (!passwordForm.currentPassword || !passwordForm.newPassword) {
    errorMessage.value = "请完整填写密码信息";
    return;
  }
  if (passwordForm.newPassword.length < 8) {
    errorMessage.value = "新密码至少需要 8 位";
    return;
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    errorMessage.value = "两次输入的新密码不一致";
    return;
  }

  submitting.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    await session.rotatePassword(passwordForm.currentPassword, passwordForm.newPassword);
    successMessage.value = "密码已更新，正在进入工作台。";
    uni.reLaunch({ url: "/pages/index/index" });
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    submitting.value = false;
  }
}

function goToRegister() {
  uni.navigateTo({ url: "/pages/register/index" });
}
</script>

<style>
.auth-layout {
  margin-top: 26rpx;
}

.register-link {
  text-align: center;
  margin-top: 20rpx;
  color: var(--cx-accent);
  font-size: 26rpx;
  cursor: pointer;
}

.narrative-stack {
  align-content: start;
}

.bullet-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.bullet-item {
  padding-left: 26rpx;
  color: var(--cx-muted);
  font-size: 24rpx;
  line-height: 1.7;
  position: relative;
}

.bullet-item::before {
  content: "";
  position: absolute;
  left: 0;
  top: 16rpx;
  width: 10rpx;
  height: 10rpx;
  border-radius: 999rpx;
  background: var(--cx-accent);
}

.mono-line {
  padding: 18rpx 20rpx;
  border-radius: 18rpx;
  background: rgba(36, 27, 21, 0.06);
  font-family: "IBM Plex Sans", monospace;
  font-size: 22rpx;
  line-height: 1.6;
  word-break: break-all;
}
</style>
