export type DeploymentSurface = "public" | "internal" | "local";
export function deploymentSurface(): DeploymentSurface {
  const configured = process.env.DEPLOYMENT_SURFACE;
  if (configured && !["public", "internal", "local"].includes(configured)) throw new Error("DEPLOYMENT_SURFACE must be public, internal, or local");
  if (process.env.VERCEL) {
    if (configured && configured !== "public") throw new Error("Vercel deployments may only expose the public/customer/learner surface");
    return "public";
  }
  return (configured as DeploymentSurface) || (process.env.NODE_ENV === "production" ? "public" : "local");
}
