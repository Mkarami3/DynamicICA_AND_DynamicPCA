import numpy as np
from visual import Plot_press
from scipy.signal import hilbert,welch
import matplotlib.pyplot as plt
from scipy.linalg import fractional_matrix_power

class ICA(object):
    
    def __init__(self, sample,No_modes):
        self.sample   = sample
        self.No_modes = No_modes
        self.func_dict = {} 
        self.func_add(lambda x: x)
        self.PCA_modes = []
        self.PCA_eigen = []
        self.ICA_modes = []
        
    def func_add(self,func):
        '''
        Adding function to the class
        '''
        
        func_id = 'id'
        self.func_dict[func_id] = func      
    
    def pre_process(self,signal):
        '''
        Remove the mean component from the sample
        and return the flucuation component
        '''
        
        signal_mean = signal.mean(axis=0).reshape(1,-1)
        
        signal_proc = (signal - np.matmul(
                  np.ones(signal.shape[0]).reshape(-1,1)
                  ,signal_mean)) 
        
        return signal_proc
    
    def PCA(self,signal_proc):
        ''' 
        Here, we used PCA to reduce the order of model.
        We apply ICA on the PCA phase space to remove orthogonality
        condition
        '''
        
        L = len(signal_proc)
        
        signal_cov = (np.dot(signal_proc.T.conj(),
                    signal_proc)/L)
        
        u, s, vh = np.linalg.svd(signal_cov, full_matrices=True)
        
        self.PCA_modes = u[:,0:self.No_modes]
        self.PCA_eigen = s[0:self.No_modes]
        
        return self.PCA_modes,s
    
    def Whitening(self,signal):
        '''
        Use whitening as a pre-step process
        '''
        signal_proc = self.pre_process(self.sample)
        self.PCA(signal_proc)
        
        PCA_eigen_diag = np.diag(self.PCA_eigen)
        dummy = fractional_matrix_power(PCA_eigen_diag, -0.5)
        dummy1= np.matmul(dummy,self.PCA_modes.T)
        
        sample_whitened = np.matmul(dummy1,signal_proc.T)
        
        return sample_whitened
#    
    def fast_ICA(self,sample_whitened):
        '''
        run fastICA algorithm to compute the ICA modes
        '''
        
        n = sample_whitened.shape[1]
        r = self.No_modes
        
        W = np.random.rand(r,sample_whitened.shape[0])
        W = W/np.linalg.norm(W, axis=-1) 
        
        counter = 0
        diff = np.Inf
        
        Tolerance = 1e-6
        counter_max = 300
        
        while (diff > Tolerance) & (counter < counter_max):
            
            counter += 1
            W_new = W
            y = np.matmul(W_new,sample_whitened)
            
            G = -np.exp(-y**2/2)
            G_deriv = y * np.exp(-y**2/2)
            
            W_1 = np.matmul(G,sample_whitened.T)/n
            W_2= G_deriv.mean(axis=1).reshape(-1,1) * W
            
            W = W_1- W_2 # Compute the non-gaussianity
            W = W/np.linalg.norm(W, axis=-1)
            
            u, s, vh = np.linalg.svd(np.array(W))
            s_inv = np.diag(np.reciprocal(s))
            
            W1 = np.matmul(u,s_inv)
            W2 = np.matmul(u.T,W)
            W  = np.matmul(W1,W2)
            
            diff = np.max(1-np.abs(np.sum(W*W_new,axis=0)))
        
        dummy = fractional_matrix_power(np.diag(self.PCA_eigen), 0.5)
        self.ICA_modes = np.matmul(np.matmul(self.PCA_modes,dummy),W) 

        
    def independent_comp(self):
        '''
        Compute the time_coefficient,or independent components,
        of each modes
        '''
        p1 = self.pre_process(self.sample)

        a = np.array(self.ICA_modes.T)
        b = np.array(p1.T)
        x = np.matmul(a,b) # Principal components
        
        return x
    
    def PSD_IC(self):
        '''
        Plot the frequency transform of time coefficient of Modes
        '''
        IC = self.independent_comp()
        
        sampling_frequency = 700
        Nfft=2**13
        
        spec_array = []
        for i in range(5):
            [freq,spec] = welch(IC[i,:],nperseg=Nfft,nfft=Nfft,
            noverlap = Nfft/2,fs = sampling_frequency)
            
            spec_array.append(spec)
        
        spec_array = np.array(spec_array)
        
        leg_list = []
        for i in range(5):
            leg_list.append('Mode %i' %(i+1))
        
        fig, ax = plt.subplots()
        for i in range(5):
            ax.plot(freq, spec_array[i,:],label=leg_list[i])
            ax.set_xlim(0,10)
            ax.set_xlabel('freq(Hz)')
            ax.set_ylabel('S(1/Hz)')
            ax.legend(loc='best')
        
    def execute(self):
        '''
        execute PCA and return PCA modes and their corresponding
        eigenvalues
        '''
        signal_whitened = self.Whitening(self.sample)
        self.fast_ICA(signal_whitened)
        
        return self.ICA_modes
    
    def visualize(self):
        
        '''
        visualizing PCA modes
        '''
        
        self.func_add(Plot_press)
        
        for i in range(self.No_modes):
            
            (self.func_dict['id'](self.ICA_modes[:,i],['red','white','blue'],
                          txt=True,num=i+1))
            
        self.PSD_IC() 
        
class Dynamic_ICA(ICA):
    
    def __init__(self,sample,No_modes,f1,f2,sampling_freq):
        
        ICA.__init__(self,sample,No_modes)
        self.f1 = f1
        self.f2 = f2
        self.fs = sampling_freq
        self.DICA_modes = []
    
    def bandpass_filter(self,signal):
        '''
        removing frequencies that lie outside the range of band pass
        '''
        
        signal_pre_proc = self.pre_process(signal)
        
        N  = len(signal_pre_proc)
        dF = self.fs/N
        
        f  = (np.linspace(start=-self.fs/2,stop=self.fs/2-dF,
                         num = self.sample.shape[0]).T)
                         
        Boolean = ((self.f1 < abs(f)) & (abs(f) < self.f2)).reshape(-1,1)
        
        FFT = np.fft.fft(signal_pre_proc,axis=0)
        FFT_shift = (np.fft.fftshift(FFT))/N
        sp = np.multiply(Boolean.astype(np.int), FFT_shift) 
        
        FFT_shift_inverse = np.fft.ifftshift(sp) 
        FFT_inverse       = np.fft.ifft(FFT_shift_inverse,axis=0)
        sample_filtered   = np.real(FFT_inverse)
        
        return sample_filtered
    
    def hilbert_trans(self,signal):
        '''
        creating analytic signal using hilbert transform
        this will remove negative frequencies in the filtered signals
        '''
        
        Signal_filtered = self.bandpass_filter(signal)
        Analytic_signal = hilbert(Signal_filtered,axis=0) 
        
        return Analytic_signal
    
    def get_modes(self,signal):
        ''' 
        return Dynamic_PCA modes
        '''
        L = len(signal)
        Analytic_signal = self.hilbert_trans(signal)
        
        signal_cov = (np.dot(Analytic_signal.T.conj(),
            Analytic_signal)/L)
        
        u, s, vh = np.linalg.svd(np.array(signal_cov))
        self.DICA_modes = u[:,0:self.No_modes]
        
    def execute(self):
        '''
        execute PCA and return PCA modes and their corresponding
        eigenvalues
        '''
        self.get_modes(self.sample)
        return self.DICA_modes
    
    def Visualize(self, mode_no):
        
        '''
        visualize the animated movie of PCA mode
        '''
        
        D_ICA = self.DICA_modes[:,mode_no]
        
        Z = D_ICA.reshape(-1,1)
        phase_shift = np.exp(1j*np.linspace(0,2*np.pi,100)).reshape(1,-1)
        
        ZZ = np.real(Z*phase_shift)
        
        self.func_add(Plot_press)
        
        plt.ion()
        for i in range(100):
            press = ZZ[:,i]
            (self.func_dict['id'](press,['red','white','blue'],
                          txt=False,num=1))
            
            plt.pause(0.1)
            plt.clf()

        
        
                