export interface ServiceEndpoints {
  agents: string;
  catalog: string;
  circulation: string;
  ill: string;
  registry: string;
}

export interface AppEnvironment {
  production: boolean;
  serviceToken: string;
  services: ServiceEndpoints;
}

export const environment: AppEnvironment = {
  production: true,
  serviceToken: 'dev-token-ai-librarian',
  services: {
    agents: '',
    catalog: '/api/catalog',
    circulation: '/api/circulation',
    ill: '/api/ill',
    registry: '/api/registry',
  },
};
