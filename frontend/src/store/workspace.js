import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  createAccount,
  deleteAccount,
  getCourseChapters,
  listAccounts,
  listCourses,
  syncCourses,
  verifyAccount,
} from "../api/accounts";
import { getNotificationConfig, testNotification, updateNotificationConfig } from "../api/notifications";
import { getStudyConfig, getTikuConfig, updateStudyConfig, updateTikuConfig } from "../api/settings";
import { cancelStudyRun, createStudyRun, getStudyRun, listStudyRuns } from "../api/study";
import { getWallet, getWalletTransactions } from "../api/wallet";

export const useWorkspaceStore = defineStore("workspace", () => {
  const accounts = ref([]);
  const runs = ref([]);
  const wallet = ref(null);
  const walletTransactions = ref([]);
  const studyConfig = ref(null);
  const tikuConfig = ref(null);
  const notificationConfig = ref(null);
  const coursesByAccount = ref({});
  const chaptersByCourse = ref({});
  const runDetails = ref({});
  const lastLoadedAt = ref("");

  const invalidAccounts = computed(() => accounts.value.filter((account) => !account.is_login_valid));
  const runningRuns = computed(() =>
    runs.value.filter((run) => ["queued", "running", "stopping"].includes(run.status)),
  );
  const completedRuns = computed(() =>
    runs.value.filter((run) => run.status === "completed"),
  );
  const failedRuns = computed(() =>
    runs.value.filter((run) => run.status === "failed"),
  );

  async function loadDashboard() {
    await Promise.all([loadAccounts(), loadRuns(), loadWallet()]);
    lastLoadedAt.value = new Date().toLocaleString();
  }

  async function loadAccounts() {
    accounts.value = await listAccounts();
    return accounts.value;
  }

  async function loadRuns() {
    runs.value = await listStudyRuns();
    return runs.value;
  }

  async function loadWallet() {
    wallet.value = await getWallet();
    return wallet.value;
  }

  async function loadWalletHistory() {
    walletTransactions.value = await getWalletTransactions();
    return walletTransactions.value;
  }

  async function loadSettings() {
    const [study, tiku] = await Promise.all([getStudyConfig(), getTikuConfig()]);
    studyConfig.value = study;
    tikuConfig.value = tiku;
    return { study, tiku };
  }

  async function saveStudyConfig(payload) {
    studyConfig.value = await updateStudyConfig(payload);
    return studyConfig.value;
  }

  async function saveTikuConfig(payload) {
    tikuConfig.value = await updateTikuConfig(payload);
    return tikuConfig.value;
  }

  async function loadNotificationConfig() {
    notificationConfig.value = await getNotificationConfig();
    return notificationConfig.value;
  }

  async function saveNotificationConfig(payload) {
    notificationConfig.value = await updateNotificationConfig(payload);
    return notificationConfig.value;
  }

  async function sendTestNotification() {
    return await testNotification();
  }

  async function addAccount(payload) {
    const account = await createAccount(payload);
    await loadAccounts();
    return account;
  }

  async function removeAccount(accountId) {
    await deleteAccount(accountId);
    delete coursesByAccount.value[accountId];
    await loadAccounts();
  }

  async function pingAccount(accountId) {
    const result = await verifyAccount(accountId);
    await loadAccounts();
    return result;
  }

  async function refreshAccountCourses(accountId) {
    const result = await syncCourses(accountId);
    coursesByAccount.value[accountId] = result.courses || [];
    await loadAccounts();
    return result;
  }

  async function loadCourses(accountId) {
    const courses = await listCourses(accountId);
    coursesByAccount.value[accountId] = courses;
    return courses;
  }

  async function loadCourseChapters(accountId, courseId) {
    const chapters = await getCourseChapters(accountId, courseId);
    chaptersByCourse.value[`${accountId}:${courseId}`] = chapters;
    return chapters;
  }

  async function createRun(payload) {
    const run = await createStudyRun(payload);
    await loadRuns();
    runDetails.value[run.id] = run;
    return run;
  }

  async function loadRunDetail(runId) {
    const detail = await getStudyRun(runId);
    runDetails.value[runId] = detail;
    await loadRuns();
    return detail;
  }

  async function cancelRun(runId) {
    const detail = await cancelStudyRun(runId);
    runDetails.value[runId] = detail;
    await loadRuns();
    return detail;
  }

  return {
    accounts,
    runs,
    wallet,
    walletTransactions,
    studyConfig,
    tikuConfig,
    notificationConfig,
    coursesByAccount,
    chaptersByCourse,
    runDetails,
    lastLoadedAt,
    invalidAccounts,
    runningRuns,
    completedRuns,
    failedRuns,
    loadDashboard,
    loadAccounts,
    loadRuns,
    loadWallet,
    loadWalletHistory,
    loadSettings,
    saveStudyConfig,
    saveTikuConfig,
    loadNotificationConfig,
    saveNotificationConfig,
    sendTestNotification,
    addAccount,
    removeAccount,
    pingAccount,
    refreshAccountCourses,
    loadCourses,
    loadCourseChapters,
    createRun,
    loadRunDetail,
    cancelRun,
  };
});
