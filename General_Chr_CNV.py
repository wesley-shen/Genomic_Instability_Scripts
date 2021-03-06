"""
Analysis for CNV data in different chromosomes
Author: Runxi Shen
"""


import os
import pandas as pd
import numpy as np
import matplotlib
import seaborn as sns
from sklearn.decomposition import PCA
from collections import defaultdict
from matplotlib import pyplot as plt
from sklearn import preprocessing
# for linux server
matplotlib.use("Agg")


# remove the duplicate columns
def uniquify(df_columns):
    seen = set()
    for item in df_columns:
        fudge = 1
        newitem = item
        while newitem in seen:
            fudge += 1
            newitem = "{}_{}".format(item, fudge)
        yield newitem
        seen.add(newitem)
    return list(seen)


def pca_scatter(pca, standardised_values, classifs):
    foo = pca.transform(standardised_values)
    bar = pd.DataFrame(list(zip(foo[:, 0], foo[:, 1], classifs)), columns=["PC1", "PC2", "Class"])
    sns.lmplot("PC1", "PC2", bar, hue="Class", fit_reg=False)
    plt.savefig("PCA_groups.png")


def pca_plot(df, cnv):
    pca = PCA(n_components=4, whiten=True)
    transf = pca.fit_transform(df)
    variance_ratio = pca.explained_variance_ratio_
    loadings = pca.components_
    # fig_sample = plt.gcf()
    # fig_sample.set_size_inches(14, 14)
    # print(transf)
    colName = df.index.tolist()
    bar = pd.DataFrame(list(zip(transf[:, 0], transf[:, 1], colName)), columns=["PC1", "PC2", "Class"])
    sns.lmplot("PC1", "PC2", bar, hue="Class", fit_reg=False, legend=False, size=5)
    plt.xlabel("PC1: " + str(round(variance_ratio[0], 3)))
    plt.ylabel("PC2: " + str(round(variance_ratio[1], 3)))
    plt.legend(loc='best')
    plt.title("PCA_plot_CNV_in_chromosomes")
    plt.savefig("PCA_" + cnv + "_Feb_12.png", bbox_inches='tight')
    PCA_loadings = pd.DataFrame(loadings, index=["PC1", "PC2", "PC3", "PC4"], columns=df.columns.tolist())
    PCA_loadings.to_csv(cnv+"_PCA_loadings_Feb_12.txt", sep="\t")


class Aneuploidy:

    """
    Group the patients of different cancer types by their genomic instability signatures (CNV in chromosomes)
    Output the files for the DGE analysis in R
    """

    def __init__(self, cancerType, RSEM_Gene_data, SNP_data, chromosome, arm, cond="loss", wdir=""):
        """

        Initialize the class with required data: DNA and RNA data of the patients with specific cancer

        :param cancerType: the cancer type of interest
        :param RSEM_Gene_data: RNA seq data of patients
        :param SNP_data: DNA segment mean data of patients
        :param chromosome: the chromosome of interest with the copy number variation (CNV)
        :param arm: the chromosomal arm of interest
        :param cond: the loss or gain signature in CNV
        :param wdir: the working directory for file output
        """
        self.cancer = cancerType
        self.rsem = RSEM_Gene_data
        self.snp = SNP_data
        self.snp_patients = pd.DataFrame()
        self.altered_chr = []
        self.normal_chr = []
        self.cond = cond
        self.chr = chromosome
        self.arm = arm
        self.samples_target = pd.DataFrame()
        self.chr_category = pd.DataFrame()
        self.instability_scores = defaultdict(float)
        self.wd = wdir
        #self.Instability_score_samples = pd.DataFrame() 


    def remove_normal_samples(self, immune):
        """
        remove the samples of normal people in the data
        :param immune: specify if the keratin and immune genes need to be removed for less noise
        :return: snp_patients
        """
        index_ = set(self.snp.index.tolist())
        normal_sample = list(filter(lambda i : i[0].split("-")[3] == ("10A"or"10B"or"11A"or"11B"or"12A"or"12B"or"13A"or"13B"or"14A"or"14B"), index_))       
        self.snp_patients = self.snp.drop(normal_sample, axis=0)
        print(self.cancer, "patients' sample number:", len(self.snp_patients.index.tolist()))
        # filter keratin and immune genes if needed
        if immune == True:
            immune_keratin_genes = pd.read_excel("/home/rshen/genomic_instability/keratin_immune_etc.xlsx", sheetname="Table S4")
            immune_keratin_gene_list = immune_keratin_genes["Gene"].tolist()
            immune_keratin_gene_list_ = list(filter(lambda i : i in self.rsem.index.tolist(), immune_keratin_gene_list))
            self.rsem.drop(immune_keratin_gene_list_, axis=0, inplace=True)
            print("immune_keratin_genes removed.")
        return self.snp_patients


    def chr_CNV(self, threshold, threshold_start=0, threshold_end=0):
        """

        :param threshold: the threshold value of segment mean to distinguish the patients with specific cnv
        :param threshold_start: the start point to cut off the specific chromosomal arm
        :param threshold_end: the end point to cut off the specific chromosomal arm
        :return: return two lists of samples, first list with the cnv, second list without the cnv
        """
        self.snp_patients = self.snp_patients.sortlevel()
        index_ = set(filter(lambda x: x[1] == self.chr, self.snp_patients.index.tolist()))
        print("length_index_chr"+str(self.chr)+": ", len(index_))
        if self.arm == "":
            for i in index_:
                segment_lengths = np.array(self.snp_patients.loc[i].End-self.snp_patients.loc[i].Start)
                segment_means = np.array(self.snp_patients.loc[i].Segment_Mean)
                check = np.dot(segment_lengths,segment_means)/sum(segment_lengths)
                if self.cond == "loss":
                    if check < -threshold:
                        self.altered_chr.append(i[0])
                    elif -threshold<check<threshold:
                        self.normal_chr.append(i[0])
                elif self.cond == "gain":
                    if check > threshold:
                        self.altered_chr.append(i[0])
                    elif -threshold<check<threshold:
                        self.normal_chr.append(i[0])
        elif self.arm == "p":
            for i in index_:
                segment_ends = np.array(self.snp_patients.loc[i].End)
                segment_starts = np.array(self.snp_patients.loc[i].Start)
                segment_means = np.array(self.snp_patients.loc[i].Segment_Mean)
                # select the probes testing the interested chromosomal arm
                segment_end = np.array(list(filter(lambda x: x < threshold_end, segment_ends)) + [threshold_end])
                segment_start = segment_starts[:len(segment_end)]
                segment_lengths = segment_end - segment_start
                segment_length = np.array(list(filter(lambda x: x > 0, segment_lengths)))
                segment_mean = segment_means[:len(segment_length)]
                check = np.dot(segment_length,segment_mean)/sum(segment_length)              
                if self.cond == "loss":
                    if check < -threshold:
                        self.altered_chr.append(i[0])
                    elif -threshold<check<threshold:
                        self.normal_chr.append(i[0])
                elif self.cond == "gain":
                    if check > threshold:
                        self.altered_chr.append(i[0])
                    elif -threshold<check<threshold:
                        self.normal_chr.append(i[0])
        elif self.arm == "q":
            for i in index_:
                segment_ends = np.array(self.snp_patients.loc[i].End)
                segment_starts = np.array(self.snp_patients.loc[i].Start)
                segment_means = np.array(self.snp_patients.loc[i].Segment_Mean)
                segment_start = np.array(list(filter(lambda x: x > threshold_start, segment_starts)) + [threshold_start])
                segment_end = segment_ends[::-1][:len(segment_start)]
                segment_lengths = segment_end - segment_start
                segment_length = np.array(list(filter(lambda x: x > 0, segment_lengths)))
                segment_mean = segment_means[::-1][:len(segment_length)]
                check = np.dot(segment_length,segment_mean)/sum(segment_length)
                if self.cond == "loss":
                    if check < -threshold:
                        self.altered_chr.append(i[0])
                    elif -threshold<check<threshold:
                        self.normal_chr.append(i[0])
                elif self.cond == "gain":
                    if check > threshold:
                        self.altered_chr.append(i[0])
                    elif -threshold<check<threshold:
                        self.normal_chr.append(i[0])
        
        print(self.cancer+"_chr_"+str(self.chr)+self.arm+self.cond+"cnv samples #: ", len(self.altered_chr)/len(index_), '\n',
              self.cancer+" normal samples #: ", len(self.normal_chr)/len(index_))
        return self.altered_chr, self.normal_chr

    def calculate_Instability_score(self):
        sample_index = set([x[0] for x in self.snp_patients.index.tolist()])
        print("Number of patient samples to calculate instability score:", len(sample_index))
        for i in sample_index:
            segments_lens = np.array(self.snp_patients.loc[i].End - self.snp_patients.loc[i].Start)
            segments_means = np.array(abs(self.snp_patients.loc[i].Segment_Mean))
            instability_score = np.dot(segments_lens, segments_means)
            skimmed_index = "-".join(i.split("-")[0:4])
            self.instability_scores[skimmed_index] = instability_score
        rsem_cols = self.rsem.columns.tolist()
        rsem_cols = ["-".join(x.split("-")[0:4]) for x in rsem_cols]
        self.rsem.columns = uniquify(rsem_cols)
        self.instability_scores = {k : v for k, v in self.instability_scores.items() if k in self.rsem.columns}
        self.Iscore = pd.DataFrame.from_dict(self.instability_scores,orient='index')
        self.Iscore.columns = ["instability_score"]
        self.Iscore.sort_values(axis=0, by="instability_score", ascending=False, inplace=True)
        self.Instability_score_samples = self.rsem[self.Iscore.index.tolist()]

    def set_samples_altered(self, indexCol):
        samples = []
        try:
            self.rsem = self.rsem.reset_index().drop_duplicates(subset = indexCol, keep='last').set_index(indexCol)
        except:
            print("Wrong input for index column name")
            
        # remove duplicate columns and rows
        rsem_cols = self.rsem.columns.tolist()
        rsem_cols = ["-".join(x.split("-")[0:4]) for x in rsem_cols]
        self.rsem = self.rsem.loc[:,~self.rsem.columns.duplicated()]
        self.rsem.columns = uniquify(rsem_cols)
        
        self.altered_chr = ["-".join(x.split("-")[0:4]) for x in self.altered_chr]
        self.altered_chr = list(uniquify(self.altered_chr))
        # self.altered_chr = list(filter(lambda i : i.split("_")[0] in self.altered_chr, self.rsem.columns))
        self.altered_chr = list(filter(lambda i: i in self.altered_chr, self.rsem.columns))
        self.normal_chr = ["-".join(x.split("-")[0:4]) for x in self.normal_chr]
        self.normal_chr = list(uniquify(self.normal_chr))
        # self.normal_chr = list(filter(lambda i : i.split("_")[0] in self.normal_chr, self.rsem.columns))
        self.normal_chr = list(filter(lambda i: i in self.normal_chr, self.rsem.columns))

#        print("altered_chr samples: ", self.altered_chr, '\n', "No_altered_chr samples: ", self.no_altered_chr)
        CNV_samples = self.altered_chr + self.normal_chr
        print(self.cancer+"_chromosome_"+str(self.chr)+self.arm+self.cond+"altered samples length: ", len(self.altered_chr)/len(rsem_cols))
        print(self.cancer+"_chromosome_"+"normal samples length: ", len(self.normal_chr)/len(rsem_cols))

        for i in CNV_samples:
            if i in self.rsem.columns.tolist():
                samples.append(i)
        self.samples_target = self.rsem[samples]
        self.samples_target.columns = list(set(uniquify(self.samples_target.columns.tolist())))
                
    def set_category(self, condition):
        self.chr_category = pd.DataFrame({"Sample_ID": self.samples_target.columns.tolist()})
        self.chr_category.set_index("Sample_ID",inplace=True)
        for i in self.chr_category.index.tolist():
            if (i.split("_")[0] in self.altered_chr):
                self.chr_category.set_value(i, "cnv", "YES")
            elif (i.split("_")[0] in self.normal_chr):
                self.chr_category.set_value(i, "cnv", "NO")
            else:
                print(i, "Error! Sample doesn't relate to chromosome "+str(self.chr)+self.arm)
        self.chr_category.sort_values(axis=0, by="chr"+str(self.chr)+self.arm+"_CNV", inplace=True)
        self.samples_target = self.samples_target[self.chr_category.index.tolist()]


    def output_(self, condition):
        """

        :param condition: the RNA seq data type, normalized or raw counts
        :return: none
        """
        self.chr_category.to_csv(self.wd+self.cancer+str(self.chr)+self.arm+"_"+self.cond+"_category_" + condition + ".txt", sep="\t")
        self.samples_target.to_csv(self.wd+self.cancer+str(self.chr)+self.arm+"_"+self.cond+"_sameples_" + condition + ".txt", sep="\t")
        #self.Iscore.to_csv(self.wd+self.cancer+"_Instability_Score_" + ".txt", sep="\t")
        #self.Instability_score_samples.to_csv(self.wd+self.cancer+"_Instability_Score_samples" + ".txt", sep="\t")

    def PCA_plot(self):
        pca = PCA(n_components=4, whiten=True)
        transf = pca.fit_transform(self.samples_target.T)
        variance_ratio = pca.explained_variance_ratio_
        loadings = pca.components_
        fig_sample = plt.gcf()
        fig_sample.set_size_inches(14,14)
        #print(transf)
        plt.xlabel("PC1: " + str(round(variance_ratio[0],3)))
        plt.ylabel("PC2: " + str(round(variance_ratio[1],3)))
        colName = self.samples_target.columns.tolist()
        for n in range(len(colName)):
            if (colName[n] in self.altered_chr):
                altered, = plt.plot(transf[n,0],transf[n,1], marker='o', markersize=8, color='red', alpha=1, label="chromosome"+str(self.chr)+self.arm+"_"+self.cond)
            if (colName[n] in self.normal_chr):
                normal, = plt.plot(transf[n,0],transf[n,1], marker='o', markersize=8, color='blue', alpha=1, label='normal_samples')
        plt.legend(loc='best', scatterpoints=1, handles=[altered, normal])
        plt.title("PCA_plot_" + self.cancer + "_"  + str(self.chr)+self.arm+"_"+self.cond)
        fig_sample.savefig(self.wd+"PCA_" + self.cancer + '_' + str(self.chr)+self.arm+"_"+self.cond + "_Jan_22.png", dpi=100)
        PCA_loadings = pd.DataFrame(loadings, index=["PC1", "PC2","PC3","PC4"], columns=self.samples_target.index.tolist())
    #        print(self.cancer, "loadings", loadings)
        PCA_loadings.to_csv(self.wd+self.cancer + "_" +str(self.chr)+self.arm+"_"+self.cond +"_PCA_loadings_Jan_22.txt", sep="\t")


def GNI(tumor, chr, arm, var, seg, RNA_, CNV_cutoff, start, end, wdir):
    aneuploidy = Aneuploidy(tumor, RNA_, seg, chr, arm, var, wdir)
    aneuploidy.remove_normal_samples(False)
    if (arm == "p"):
        aneuploidy.chr_CNV(threshold=CNV_cutoff, threshold_start=start, threshold_end=end)
    elif (arm == "q"):
        aneuploidy.chr_CNV(threshold=CNV_cutoff, threshold_start=start, threshold_end=end)
    else:
        aneuploidy.chr_CNV(threshold=CNV_cutoff)

    print(tumor,chr, arm, "Grouping done.")
    aneuploidy.set_samples_altered("GeneSymbol")
    print(tumor, chr, arm, "samples filtering done.")
    aneuploidy.set_category("normalized")
    print(tumor, chr, arm, "GSEA preparation done.")
    #aneuploidy.PCA_plot()
    aneuploidy.output_("raw_counts")
    print("Output done.")
    return aneuploidy

if __name__ == '__main__':
    wd = "/home/rshen/genomic_instability/chromosome8p/LOH_8p_paper/cnv_correlation_DGE/"
    os.chdir(wd)

    # Investigate the CNV in chromosome 1q gain, 3 loss, 6p gain, 6q loss, 8p loss, 8q gain, 9p loss, 18q loss
    chr_alter_dict = {"loss": [(3, ''), (6, 'q'), (8, 'p'), (9, 'p'), (18, 'q')],
                      "gain": [(1, 'q'), (6, 'p'), (8, 'q'),(5, 'q')]}
    # each chromosome arm's cutoff value in segment files
    chr_arm_cufoff = {(3, ''): (0, 0), (6, 'q'): (6.0E7, 1.7E8), (8, 'p'): (2E7, 4.5E7), (9, 'p'): (5.0E7, 1.4E8), (6, 'p'): (1E6, 6.0E7),
                      (8, 'q'): (4.8E7, 1.5E8), (1, 'q'): (1.3E8, 2.5E8), (5, 'q'): (5E7, 1.8E8),  (18, 'q'): (1.9E7, 7.7E7)}
    
    # read in the segment file and RNA data
    BRCA_ = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/BRCA__CNV.seg.txt", index_col=[0,1])
    # BRCA_RNA = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/BRCA_normalized_results_simplified.txt", index_col=0)
    BRCA_RNA = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/BRCA_genes_results_processed_raw_counts.txt", index_col=0)

    SKCM_ = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/SKCM__CNV.seg.txt", index_col=[0,1])
    # SKCM_RNA = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/SKCM_normalized_results_simplified.txt", index_col=0)
    SKCM_RNA = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/SKCM_genes_results_processed_raw_counts.txt", index_col=0)

    UVM_ = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/UVM__broad.mit.edu__genome_wide_snp_6__nocnv_hg19__Aug-04-2015.seg.txt", index_col=[0,1])
    # UVM_RNA = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/UVM_normalized_results_processed_No_keratin_immune.txt", index_col=0)
    UVM_RNA = pd.read_table("/home/rshen/genomic_instability/chromosome8p/TCGA_data/UVM_raw_counts_.txt", index_col=0)

    # for variation in chr_alter_dict.keys():
    #     for chr_arm in chr_alter_dict[variation]:
    #         aneuploidy = GNI("UVM0.2", chr_arm[0], chr_arm[1], variation, UVM_, UVM_RNA, 0.2, 
    #                          start=chr_arm_cufoff[chr_arm][0], end=chr_arm_cufoff[chr_arm][1], wdir=wd)
    #         # samples = aneuploidy.samples_target
            # altered_chr = aneuploidy.altered_chr
            # altered_samples = samples[altered_chr]
            # standardized = preprocessing.scale(altered_samples).T
            # standardized = pd.DataFrame(standardized, index=altered_samples.columns,
            #                             columns=altered_samples.index)
            # # screenplot(pca, standardized)
            # # pca_scatter(pca, standardized, standardized.index)
            # # pca_plot(standardized)
            # pca_plot(altered_samples.T, str(chr_arm[0])+chr_arm[1]+variation)
            # genomic_instability_df['{}_{}_{}'.format(chr_arm[0],chr_arm[1],variation)] = altered_samples.mean(axis=1)
            # genomic_instability_df.to_csv(wd+"BRCA_GID_thres_0.2.txt", sep='\t')
    

    for variation in chr_alter_dict.keys():
        for chr_arm in chr_alter_dict[variation]:
            aneuploidy = GNI("BRCA0.2", chr_arm[0], chr_arm[1], variation, BRCA_, BRCA_RNA, 0.2, 
                         start=chr_arm_cufoff[chr_arm][0], end=chr_arm_cufoff[chr_arm][1], wdir=wd)
            # samples = aneuploidy.samples_target
            # altered_chr = aneuploidy.altered_chr
            # altered_samples = samples[altered_chr]
            # standardized = preprocessing.scale(altered_samples).T
            # standardized = pd.DataFrame(standardized, index=altered_samples.columns,
            #                             columns=altered_samples.index)
            # # screenplot(pca, standardized)
            # # pca_scatter(pca, standardized, standardized.index)
            # # pca_plot(standardized)
            # pca_plot(altered_samples.T, str(chr_arm[0])+chr_arm[1]+variation)
            # genomic_instability_df['{}_{}_{}'.format(chr_arm[0],chr_arm[1],variation)] = altered_samples.mean(axis=1)
            # genomic_instability_df.to_csv(wd+"UVM_GID_thres_0.2.txt", sep='\t')
    

    # for variation in chr_alter_dict.keys():
    #     for chr_arm in chr_alter_dict[variation]:
    #         aneuploidy = GNI("SKCM0.2", chr_arm[0], chr_arm[1], variation, SKCM_, SKCM_RNA, 0.2, 
    #                         start=chr_arm_cufoff[chr_arm][0], end=chr_arm_cufoff[chr_arm][1], wdir=wd)
            # samples = aneuploidy.samples_target
            # altered_chr = aneuploidy.altered_chr
            # altered_samples = samples[altered_chr]
            # standardized = preprocessing.scale(altered_samples).T
            # standardized = pd.DataFrame(standardized, index=altered_samples.columns,
            #                             columns=altered_samples.index)
            # # screenplot(pca, standardized)
            # # pca_scatter(pca, standardized, standardized.index)
            # # pca_plot(standardized)
            # pca_plot(altered_samples.T, str(chr_arm[0])+chr_arm[1]+variation)
            # genomic_instability_df['{}_{}_{}'.format(chr_arm[0],chr_arm[1],variation)] = altered_samples.mean(axis=1)
            # genomic_instability_df.to_csv(wd+"SKCM_GID_thres_0.2.txt", sep='\t')

    # calculate instability scores
    """
    BRCA_gainof1q = Aneuploidy("BRCA", BRCA_RNA, BRCA_, 1, "q", "gain")
    BRCA_gainof1q.remove_normal_samples(False)
    BRCA_gainof1q.calculate_Instability_score()
    BRCA_gainof1q.output_("")

    SKCM_lossOf18q = Aneuploidy("SKCM", SKCM_RNA, SKCM_, 18, "q", "loss")
    SKCM_lossOf18q.remove_normal_samples(False)
    SKCM_lossOf18q.calculate_Instability_score()
    SKCM_lossOf18q.output_("")

    UVM_lossOf18q = Aneuploidy("UVM", UVM_RNA, UVM_, 18, "q", "loss")
    UVM_lossOf18q.remove_normal_samples()
    UVM_lossOf18q.calculate_Instability_score(False)
    UVM_lossOf18q.output_("")
    """
