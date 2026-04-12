import { apiRequest } from "./client";

export function getWallet() {
  return apiRequest("/wallet");
}

export function getWalletTransactions() {
  return apiRequest("/wallet/transactions");
}

export function createRecharge(payload) {
  return apiRequest("/wallet/recharge", {
    method: "POST",
    data: payload,
  });
}
