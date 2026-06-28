resource "neon_project" "database" {
  count = var.manage_neon ? 1 : 0

  name           = "${local.name_prefix}-db"
  pg_version     = var.neon_pg_version
  region_id      = var.neon_region_id
  store_password = "yes"

  branch {
    name          = var.neon_branch_name
    database_name = var.neon_database_name
    role_name     = var.neon_owner_role
  }

  default_endpoint_settings {
    autoscaling_limit_min_cu = var.neon_min_cu
    autoscaling_limit_max_cu = var.neon_max_cu
    suspend_timeout_seconds  = var.neon_suspend_timeout_seconds
  }
}

resource "neon_role" "app" {
  count = var.manage_neon ? 1 : 0

  project_id = neon_project.database[0].id
  branch_id  = neon_project.database[0].default_branch_id
  name       = var.neon_app_role
}
