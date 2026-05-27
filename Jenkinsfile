// ============================================================================
// Jenkinsfile — Buea Market Watch CI/CD Pipeline
// ============================================================================
// Five sequential stages:
//   1. Repository Pull
//   2. Test Execution Matrix
//   3. Immutable Docker Assembly
//   4. Artifact Registration (Nexus / JFrog Artifactory)
//   5. Automated Infrastructure Fabric Release
// ============================================================================

pipeline {
    agent any

    environment {
        // Private Docker registry hosted on Sonatype Nexus / JFrog Artifactory
        REGISTRY                = 'nexus.bueamarketwatch.internal:8082'
        IMAGE_NAME              = 'market-watch-backend'

        // Jenkins credential IDs (configured under Manage Jenkins → Credentials)
        REGISTRY_CREDENTIALS_ID = 'nexus-registry-auth-token'
        SSH_CREDENTIALS_ID      = 'production-server-ssh-key'
    }

    stages {

        // --------------------------------------------------------------------
        // Stage 1: Pull the latest source from version control
        // --------------------------------------------------------------------
        stage('Repository Pull') {
            steps {
                checkout scm
            }
        }

        // --------------------------------------------------------------------
        // Stage 2: Install dependencies and run the full test matrix
        //          --maxfail=1 aborts on the first failure to give fast feedback
        // --------------------------------------------------------------------
        stage('Test Execution Matrix') {
            steps {
                sh '''
                    python -m pip install --quiet -r requirements.txt
                    pytest --maxfail=1 --disable-warnings -v
                '''
            }
        }

        // --------------------------------------------------------------------
        // Stage 3: Build an immutable, build-numbered Docker image
        //          The tag is the unique Jenkins BUILD_NUMBER ensuring every
        //          artefact is traceable back to its originating pipeline run.
        // --------------------------------------------------------------------
        stage('Immutable Docker Assembly') {
            steps {
                script {
                    appImage = docker.build("${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}")
                }
            }
        }

        // --------------------------------------------------------------------
        // Stage 4: Push the image to the private Nexus / Artifactory registry
        //          Both the build-specific tag and 'latest' are pushed so that
        //          rollback (by tag) and fast re-deploy (via 'latest') are both
        //          supported.
        // --------------------------------------------------------------------
        stage('Artifact Registration') {
            steps {
                script {
                    docker.withRegistry("https://${REGISTRY}", REGISTRY_CREDENTIALS_ID) {
                        appImage.push("${BUILD_NUMBER}")
                        appImage.push('latest')
                    }
                }
            }
        }

        // --------------------------------------------------------------------
        // Stage 5: SSH into the production host, authenticate against the
        //          registry, pull the new image, and hot-swap the container.
        //          Python Fabric handles the remote orchestration logic.
        // --------------------------------------------------------------------
        stage('Automated Infrastructure Fabric Release') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: REGISTRY_CREDENTIALS_ID,
                        usernameVariable: 'REGISTRY_USER',
                        passwordVariable: 'REGISTRY_PASS'
                    )
                ]) {
                    sshagent([SSH_CREDENTIALS_ID]) {
                        sh """
                            pip install --quiet fabric
                            fab deploy --image-tag=${BUILD_NUMBER}
                        """
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // Post-pipeline notifications
    // ------------------------------------------------------------------------
    post {
        success {
            echo "Pipeline succeeded. Build ${BUILD_NUMBER} is live."
        }
        failure {
            echo "Pipeline FAILED at stage. Review the console output above."
        }
        always {
            // Remove dangling intermediate Docker layers to keep the build
            // agent disk healthy across many pipeline runs.
            sh 'docker image prune -f || true'
        }
    }
}
