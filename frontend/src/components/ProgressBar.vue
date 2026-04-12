<template>
  <view class="cx-progress">
    <view class="cx-progress-bar">
      <view
        class="cx-progress-fill"
        :class="statusClass"
        :style="{ width: clampedPercent + '%' }"
      />
    </view>
    <text class="cx-progress-label">{{ clampedPercent }}%</text>
  </view>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  percent: {
    type: Number,
    default: 0,
  },
  status: {
    type: String,
    default: "running",
  },
});

const clampedPercent = computed(() => Math.min(100, Math.max(0, Math.round(props.percent))));

const statusClass = computed(() => {
  if (props.status === "succeeded") return "cx-progress-fill--ok";
  if (props.status === "failed" || props.status === "cancelled") return "cx-progress-fill--bad";
  return "cx-progress-fill--active";
});
</script>

<style>
.cx-progress {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.cx-progress-bar {
  flex: 1;
  height: 16rpx;
  border-radius: 999rpx;
  background: rgba(76, 53, 32, 0.1);
  overflow: hidden;
}

.cx-progress-fill {
  height: 100%;
  border-radius: 999rpx;
  transition: width 0.4s ease;
}

.cx-progress-fill--active {
  background: linear-gradient(90deg, var(--cx-accent), #c36f34);
  animation: cx-progress-pulse 1.5s ease-in-out infinite;
}

.cx-progress-fill--ok {
  background: var(--cx-olive);
}

.cx-progress-fill--bad {
  background: var(--cx-alert);
}

.cx-progress-label {
  min-width: 80rpx;
  color: var(--cx-muted);
  font-size: 24rpx;
  font-weight: 600;
  text-align: right;
}

@keyframes cx-progress-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.75; }
}
</style>
