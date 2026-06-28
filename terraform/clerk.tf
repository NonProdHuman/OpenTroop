resource "terraform_data" "clerk_jwt_template" {
  count = var.manage_clerk_jwt_template ? 1 : 0

  input = {
    claims_hash   = sha256(jsonencode(var.clerk_jwt_claims))
    template_name = var.clerk_jwt_template_name
  }

  provisioner "local-exec" {
    command = "${path.module}/scripts/configure-clerk-jwt-template.sh"

    environment = {
      CLERK_JWT_CLAIMS_JSON   = jsonencode(var.clerk_jwt_claims)
      CLERK_JWT_TEMPLATE      = var.clerk_jwt_template_name
      CLERK_SECRET_KEY        = var.clerk_secret_key
      CLERK_TEMPLATE_LIFETIME = "3600"
    }
  }
}
