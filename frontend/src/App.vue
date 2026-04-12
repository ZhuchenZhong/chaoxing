<template>
  <slot />
</template>

<script setup>
</script>

<style>
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Noto+Serif+SC:wght@500;600;700&display=swap");

:root {
  --cx-bg: #efe4cf;
  --cx-bg-soft: #f8f2e6;
  --cx-panel: rgba(255, 250, 242, 0.88);
  --cx-panel-strong: rgba(255, 249, 238, 0.97);
  --cx-line: rgba(77, 53, 32, 0.14);
  --cx-text: #241b15;
  --cx-muted: #76614c;
  --cx-accent: #9d4f1f;
  --cx-accent-dark: #6c3410;
  --cx-olive: #305243;
  --cx-alert: #9d2f2f;
  --cx-shadow: 0 24rpx 60rpx rgba(70, 41, 21, 0.12);
  --cx-radius-lg: 34rpx;
  --cx-radius-md: 24rpx;
  --cx-radius-sm: 18rpx;
}

page {
  min-height: 100%;
  background:
    radial-gradient(circle at top left, rgba(201, 138, 79, 0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(48, 82, 67, 0.12), transparent 24%),
    linear-gradient(180deg, #f3ead8 0%, #efe4cf 38%, #e9ddc7 100%);
  color: var(--cx-text);
  font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif;
}

view,
text,
button,
input,
textarea,
picker,
scroll-view {
  box-sizing: border-box;
}

button::after {
  border: none;
}

.cx-shell {
  position: relative;
  min-height: 100vh;
  padding: 42rpx 28rpx 140rpx;
}

.cx-shell::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(102, 78, 57, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(102, 78, 57, 0.035) 1px, transparent 1px);
  background-size: 30rpx 30rpx;
  opacity: 0.35;
}

.cx-topbar {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 22rpx;
  padding: 32rpx;
  border: 1px solid var(--cx-line);
  border-radius: var(--cx-radius-lg);
  background: linear-gradient(145deg, rgba(255, 250, 242, 0.94), rgba(246, 235, 214, 0.85));
  backdrop-filter: blur(18px);
  box-shadow: var(--cx-shadow);
  overflow: hidden;
}

.cx-topbar::after {
  content: "";
  position: absolute;
  width: 200rpx;
  height: 200rpx;
  right: -60rpx;
  top: -80rpx;
  border-radius: 999rpx;
  background: rgba(157, 79, 31, 0.11);
}

.cx-brand-row {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
  align-items: flex-start;
}

.cx-kicker {
  display: inline-flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 14rpx;
  color: var(--cx-accent-dark);
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.cx-kicker::before {
  content: "";
  width: 30rpx;
  height: 2px;
  background: currentColor;
  opacity: 0.75;
}

.cx-title {
  display: block;
  max-width: 90%;
  font-family: "Noto Serif SC", "Source Han Serif SC", serif;
  font-size: 54rpx;
  line-height: 1.08;
  font-weight: 700;
}

.cx-subtitle {
  display: block;
  margin-top: 16rpx;
  max-width: 92%;
  color: var(--cx-muted);
  font-size: 26rpx;
  line-height: 1.7;
}

.cx-meta {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16rpx;
  align-items: center;
}

.cx-user-chip,
.cx-status-chip {
  display: inline-flex;
  align-items: center;
  gap: 10rpx;
  padding: 14rpx 18rpx;
  border-radius: 999rpx;
  background: rgba(36, 27, 21, 0.06);
  color: var(--cx-text);
  font-size: 22rpx;
  font-weight: 600;
}

.cx-user-chip--admin,
.cx-status-chip--admin {
  background: rgba(48, 82, 67, 0.12);
  color: var(--cx-olive);
}

.cx-nav {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.cx-nav-btn,
.cx-inline-btn,
.cx-ghost-btn,
.cx-primary-btn,
.cx-danger-btn {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  gap: 10rpx;
  min-height: 78rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  border: 1px solid transparent;
  font-size: 24rpx;
  font-weight: 600;
  line-height: 1;
  transition: transform 120ms ease, opacity 120ms ease;
}

.cx-nav-btn {
  background: rgba(255, 255, 255, 0.62);
  border-color: rgba(80, 56, 34, 0.08);
  color: var(--cx-muted);
}

.cx-nav-btn--active {
  background: var(--cx-text);
  color: #fbf7f0;
}

.cx-primary-btn {
  background: linear-gradient(135deg, var(--cx-accent), #c36f34);
  color: #fffaf4;
  box-shadow: 0 14rpx 32rpx rgba(157, 79, 31, 0.22);
}

.cx-ghost-btn,
.cx-inline-btn {
  background: rgba(255, 255, 255, 0.65);
  border-color: rgba(80, 56, 34, 0.08);
  color: var(--cx-text);
}

.cx-danger-btn {
  background: rgba(157, 47, 47, 0.1);
  color: var(--cx-alert);
}

.cx-inline-btn {
  min-height: 64rpx;
  padding: 0 18rpx;
  font-size: 22rpx;
}

.cx-grid {
  display: grid;
  gap: 20rpx;
  margin-top: 24rpx;
}

.cx-grid--triple {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.cx-grid--double {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.cx-panel {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  padding: 28rpx;
  border: 1px solid var(--cx-line);
  border-radius: var(--cx-radius-md);
  background: var(--cx-panel);
  box-shadow: 0 16rpx 42rpx rgba(66, 43, 23, 0.08);
}

.cx-panel--strong {
  background: var(--cx-panel-strong);
}

.cx-panel-title {
  font-family: "Noto Serif SC", "Source Han Serif SC", serif;
  font-size: 34rpx;
  line-height: 1.25;
  font-weight: 600;
}

.cx-panel-subtitle {
  color: var(--cx-muted);
  font-size: 24rpx;
  line-height: 1.7;
}

.cx-metric-value {
  font-family: "Noto Serif SC", serif;
  font-size: 58rpx;
  line-height: 1;
  font-weight: 700;
}

.cx-metric-label {
  color: var(--cx-muted);
  font-size: 22rpx;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.cx-alert {
  padding: 20rpx 22rpx;
  border-radius: var(--cx-radius-sm);
  background: rgba(157, 47, 47, 0.08);
  color: var(--cx-alert);
  font-size: 24rpx;
  line-height: 1.7;
}

.cx-success {
  padding: 20rpx 22rpx;
  border-radius: var(--cx-radius-sm);
  background: rgba(48, 82, 67, 0.1);
  color: var(--cx-olive);
  font-size: 24rpx;
  line-height: 1.7;
}

.cx-form {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.cx-field-label {
  display: block;
  margin-bottom: 10rpx;
  color: var(--cx-muted);
  font-size: 22rpx;
  font-weight: 600;
}

.cx-input,
.cx-textarea,
.cx-picker {
  width: 100%;
  min-height: 88rpx;
  padding: 0 24rpx;
  border: 1px solid rgba(76, 53, 32, 0.12);
  border-radius: 22rpx;
  background: rgba(255, 252, 247, 0.95);
  color: var(--cx-text);
  font-size: 26rpx;
}

.cx-input {
  display: flex;
  align-items: center;
}

.cx-picker {
  display: flex;
  align-items: center;
}

.cx-textarea {
  min-height: 240rpx;
  padding-top: 20rpx;
  padding-bottom: 20rpx;
  line-height: 1.6;
}

.cx-field-hint {
  color: var(--cx-muted);
  font-size: 22rpx;
  line-height: 1.6;
}

.cx-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  align-items: center;
}

.cx-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.cx-list-item {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  padding: 22rpx 24rpx;
  border: 1px solid rgba(76, 53, 32, 0.1);
  border-radius: 22rpx;
  background: rgba(255, 252, 247, 0.72);
}

.cx-item-top {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  align-items: flex-start;
}

.cx-item-title {
  font-size: 28rpx;
  font-weight: 700;
  line-height: 1.4;
}

.cx-item-meta {
  color: var(--cx-muted);
  font-size: 22rpx;
  line-height: 1.7;
}

.cx-section-label {
  color: var(--cx-muted);
  font-size: 22rpx;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.cx-empty {
  padding: 32rpx 24rpx;
  border-radius: 22rpx;
  background: rgba(255, 253, 249, 0.76);
  color: var(--cx-muted);
  font-size: 24rpx;
  line-height: 1.7;
  text-align: center;
}

.cx-footer-mark {
  position: fixed;
  right: 22rpx;
  bottom: calc(18rpx + env(safe-area-inset-bottom));
  z-index: 12;
  padding: 12rpx 18rpx;
  border-radius: 999rpx;
  background: rgba(36, 27, 21, 0.08);
  color: rgba(36, 27, 21, 0.65);
  font-size: 20rpx;
}

@media (min-width: 960px) {
  .cx-shell {
    max-width: 1240px;
    margin: 0 auto;
    padding-top: 38rpx;
  }

  .cx-grid--triple {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .cx-grid--double {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 959px) {
  .cx-grid--triple,
  .cx-grid--double {
    grid-template-columns: minmax(0, 1fr);
  }

  .cx-title {
    max-width: 100%;
  }
}
</style>
