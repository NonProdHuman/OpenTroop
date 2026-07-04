import * as SecureStore from "expo-secure-store"
import { deleteTenantDatabases } from "@/data/expo-db"
import { ACTIVE_TENANT_KEY, KNOWN_TENANTS_KEY, getKnownTenantIds } from "./tenant-context"

/**
 * Sign-out wipe (GH-153 §C5): the device's local data belongs to an identity,
 * not the device. Deletes every tenant database file, the pending queues
 * inside them, and the persisted tenant selection.
 */
export async function wipeAllLocalData(): Promise<void> {
  const tenantIds = await getKnownTenantIds()
  deleteTenantDatabases(tenantIds)
  await SecureStore.deleteItemAsync(ACTIVE_TENANT_KEY)
  await SecureStore.deleteItemAsync(KNOWN_TENANTS_KEY)
}
