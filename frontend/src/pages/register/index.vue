<template>
  <AppShell
    active-path="/pages/register/index"
    eyebrow="Account Registration"
    title="注册新账号"
    subtitle="填写以下信息创建你的工作台账号。"
  >
    <view class="cx-grid register-layout">
      <view class="cx-panel cx-panel--strong">
        <text class="cx-panel-title">创建账号</text>
        <text class="cx-panel-subtitle">
          需要有效的邀请码才能注册。所有带 * 的字段为必填项。
        </text>

        <view v-if="errorMessage" class="cx-alert">{{ errorMessage }}</view>
        <view v-if="successMessage" class="cx-success">{{ successMessage }}</view>

        <view class="cx-form">
          <view>
            <text class="cx-field-label">邀请码 *</text>
            <input
              v-model="form.invite_code"
              class="cx-input"
              placeholder="输入邀请码"
            />
          </view>
          <view>
            <text class="cx-field-label">邮箱 *</text>
            <input
              v-model="form.email"
              class="cx-input"
              type="text"
              placeholder="输入邮箱地址"
            />
          </view>
          <view>
            <text class="cx-field-label">用户名 *</text>
            <input
              v-model="form.username"
              class="cx-input"
              placeholder="3-50 个字符"
            />
          </view>
          <view>
            <text class="cx-field-label">密码 *</text>
            <input
              v-model="form.password"
              class="cx-input"
              password
              placeholder="至少 8 位"
            />
          </view>
          <view>
            <text class="cx-field-label">确认密码 *</text>
            <input
              v-model="form.confirmPassword"
              class="cx-input"
              password
              placeholder="再次输入密码"
            />
          </view>
          <view>
            <text class="cx-field-label">显示名称（可选）</text>
            <input
              v-model="form.display_name"
              class="cx-input"
              placeholder="留空则使用用户名"
            />
          </view>
          <button class="cx-primary-btn" :disabled="submitting" @click="submitRegister">
            {{ submitting ? "注册中..." : "注册" }}
          </button>
          <view class="login-link" @click="goToLogin">
            <text>已有账号？登录</text>
          </view>
        </view>
      </view>
    </view>
  </AppShell>
</template>

<script setup>
import { reactive, ref } from "vue";

import AppShell from "../../components/AppShell.vue";
import { register } from "../../api/auth";
import { extractErrorMessage } from "../../utils/display";

const submitting = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const form = reactive({
  invite_code: "",
  email: "",
  username: "",
  password: "",
  confirmPassword: "",
  display_name: "",
});

function validate() {
  if (!form.invite_code.trim()) {
    return "请输入邀请码";
  }
  if (!form.email.trim()) {
    return "请输入邮箱地址";
  }
  if (!form.username.trim()) {
    return "请输入用户名";
  }
  if (form.username.trim().length < 3 || form.username.trim().length > 50) {
    return "用户名长度需要在 3-50 个字符之间";
  }
  if (!form.password) {
    return "请输入密码";
  }
  if (form.password.length < 8) {
    return "密码至少需要 8 位";
  }
  if (form.password !== form.confirmPassword) {
    return "两次输入的密码不一致";
  }
  return null;
}

async function submitRegister() {
  const err = validate();
  if (err) {
    errorMessage.value = err;
    return;
  }

  submitting.value = true;
  errorMessage.value = "";
  successMessage.value = "";

  const payload = {
    invite_code: form.invite_code.trim(),
    email: form.email.trim(),
    username: form.username.trim(),
    password: form.password,
  };
  if (form.display_name.trim()) {
    payload.display_name = form.display_name.trim();
  }

  try {
    await register(payload);
    successMessage.value = "注册成功！正在跳转到登录页面...";
    setTimeout(() => {
      uni.redirectTo({ url: "/pages/login/index" });
    }, 2000);
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    submitting.value = false;
  }
}

function goToLogin() {
  uni.navigateBack({
    fail: () => {
      uni.redirectTo({ url: "/pages/login/index" });
    },
  });
}
</script>

<style>
.register-layout {
  margin-top: 26rpx;
}

.login-link {
  text-align: center;
  margin-top: 20rpx;
  color: var(--cx-accent);
  font-size: 26rpx;
  cursor: pointer;
}
</style>
