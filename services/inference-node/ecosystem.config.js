module.exports = {
  apps: [
    // ═══════════════════════════════════════════════════════════════════════════
    // 3-MODEL CONFIGURATION (fits in 24GB RTX 3090):
    //   Port 8080: BiMediX2-8B      (6.1GB)  - Clinical, AIDoctor, Chat, MedicalQA (PRIMARY)
    //   Port 8082: Qwen-0.6B        (1.1GB)  - Ultra-fast Scribe/Triage
    //   Port 8083: OpenInsurance-8B (5.3GB)  - Billing, Claims, Insurance
    // Total VRAM: ~12.5GB (fits 24GB GPU comfortably)
    // ═══════════════════════════════════════════════════════════════════════════
    
    // Primary endpoint - BiMediX2-8B (Port 8080) - Best for clinical/AI Doctor
    {
      name: 'llama-primary-8080',
      script: '/home/dgs/llama.cpp/build/bin/llama-server',
      args: [
        '-m', '/home/dgs/N3090/services/inference-node/models/BiMediX2-8B-hf.i1-Q6_K.gguf',
        '-c', '8192',
        '-ngl', '99',
        '--port', '8080',
        '--host', '0.0.0.0',
        '--api-key', process.env.API_KEY_PRIMARY_8080 || 'dev-key',
      ],
      env: { CUDA_VISIBLE_DEVICES: '0' },
      autorestart: true,
      max_memory_restart: '10G',
      error_file: './logs/llama-8080-error.log',
      out_file: './logs/llama-8080-out.log',
    },
    
    // Tier 0: Qwen-0.6B (Port 8082) - Ultra-fast Scribe
    {
      name: 'llama-qwen-8082',
      script: '/home/dgs/llama.cpp/build/bin/llama-server',
      args: [
        '-m', '/home/dgs/N3090/services/inference-node/models/qwen-0.6b-medicaldataset-f16.gguf',
        '-c', '2048',
        '-ngl', '99',
        '--port', '8082',
        '--host', '0.0.0.0',
        '--api-key', process.env.API_KEY_QWEN_8082 || 'dev-key',
      ],
      env: { CUDA_VISIBLE_DEVICES: '0' },
      autorestart: true,
      max_memory_restart: '2G',
      error_file: './logs/llama-8082-error.log',
      out_file: './logs/llama-8082-out.log',
    },
    
    // Tier 2: OpenInsurance-8B (Port 8083) - Billing, Claims
    {
      name: 'llama-openins-8083',
      script: '/home/dgs/llama.cpp/build/bin/llama-server',
      args: [
        '-m', '/home/dgs/N3090/services/inference-node/models/openinsurancellm-llama3-8b.Q5_K_M.gguf',
        '-c', '4096',
        '-ngl', '99',
        '--port', '8083',
        '--host', '0.0.0.0',
        '--api-key', process.env.API_KEY_OPENINSURANCE_8083 || 'dev-key',
      ],
      env: { CUDA_VISIBLE_DEVICES: '0' },
      autorestart: true,
      max_memory_restart: '10G',
      error_file: './logs/llama-8083-error.log',
      out_file: './logs/llama-8083-out.log',
    },
  ],
};
